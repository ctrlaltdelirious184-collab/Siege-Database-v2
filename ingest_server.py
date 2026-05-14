"""
ingest_server.py — Local HTTP server for real-time SWEX plugin data ingestion.

Runs on localhost:7831 in a daemon thread inside Siege Database.
The SWEX plugin POSTs individual GetGuildSiegeBattleLog entries here
and the app processes them instantly without any user interaction.

Endpoints:
  GET  /health  → {"status": "running", "port": ..., "wizard_name": "..."}
  POST /ingest  → processes a single battle_log_list entry
  POST /discovery → processes tower clicks/rankings
  OPTIONS *     → CORS preflight (for safety)
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

_server_instance = None
_refresh_callback = None
_notify_callback = None
_discovery_callback = None
_wizard_name_getter = None
_last_contact = 0  # Unix timestamp
PORT = 7831


# ── Handler ───────────────────────────────────────────────

class _IngestHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # Suppress default stdout logging

    # ── CORS preflight
    def do_OPTIONS(self):
        self._send(204, b"")

    # ── Health check — plugin uses this as a heartbeat
    def do_GET(self):
        global _last_contact
        if self.path == "/health":
            _last_contact = time.time()
            import database as db
            wiz = _wizard_name_getter() if _wizard_name_getter else ""
            scout = db.get_setting("auto_discovery", "True") == "True"
            all_guild = db.get_setting("import_all_guild", "False") == "True"
            self._json(200, {
                "status": "running", 
                "port": PORT, 
                "wizard_name": wiz,
                "scouting_enabled": scout,
                "import_all_guild": all_guild
            })
        else:
            self._json(404, {"error": "not found"})

    # ── Ingest a single battle entry or discovery packet
    def do_POST(self):
        if self.path == "/discovery":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                packet = json.loads(body.decode("utf-8"))
                
                import database as db
                import importer
                
                # Only process if scouting is enabled
                if db.get_setting("auto_discovery", "True") == "True":
                    count = importer.process_discovery(packet.get("type"), packet.get("data"))
                    self._json(200, {"status": "ok", "count": count})
                    
                    # Refresh UI to show newly discovered defenses
                    if _refresh_callback:
                        _refresh_callback()
                    if _discovery_callback:
                        _discovery_callback(count)
                else:
                    self._json(200, {"status": "disabled"})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return

        if self.path != "/ingest":
            self._json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            entry = json.loads(body.decode("utf-8"))
        except Exception as e:
            self._json(400, {"error": f"bad request: {e}"})
            return

        try:
            import importer
            wiz = _wizard_name_getter() if _wizard_name_getter else ""
            
            import os as _os, json as _json
            _log_path = _os.path.join(_os.path.dirname(__file__), "debug.log")
            
            with open(_log_path, "a", encoding="utf-8") as _lf:
                _lf.write(f"--- [INGEST START] ---\n")
                _lf.write(f"Entry Wizard: '{entry.get('wizard_name')}' | Filter: '{wiz}'\n")
                _lf.write(f"Log ID: {entry.get('log_id')}\n")
                
                deck = entry.get("view_battle_deck_info")
                if deck:
                    _lf.write(f"Deck Info: FOUND (len={len(deck)})\n")
                else:
                    _lf.write(f"Deck Info: MISSING\n")
                    _lf.write(f"Full Data: {_json.dumps(entry, indent=2)}\n")
                _lf.write(f"--- [INGEST END] ---\n\n")
            
            result = importer.process_live_battle(entry, wiz)
            
            if result.get("status") == "skipped":
                print(f" [!] Battle skipped: {result.get('reason')}")
            elif result.get("status") == "duplicate":
                print(f" [-] Battle skipped: Duplicate (ID: {entry.get('log_id')})")
            elif result.get("status") == "ok":
                print(f" [+] Battle imported! {result.get('offense')} vs {result.get('defense')}")
                
            self._json(200, result)

            if result.get("status") == "ok":
                # Schedule UI refresh on the main tkinter thread
                if _refresh_callback:
                    _refresh_callback()
                if _notify_callback:
                    _notify_callback(result)

        except Exception as e:
            self._json(500, {"error": str(e)})

    # ── Helpers
    def _json(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self._send(code, body, "application/json")

    def _send(self, code, body, content_type="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if body:
            self.wfile.write(body)


# ── Public API ────────────────────────────────────────────

def start(refresh_cb=None, notify_cb=None, discovery_cb=None, wizard_getter=None, port=7831):
    """
    Start the ingest server in a background daemon thread.
    """
    global _server_instance, _refresh_callback, _notify_callback, _discovery_callback, _wizard_name_getter, PORT

    PORT = port
    _refresh_callback = refresh_cb
    _notify_callback = notify_cb
    _discovery_callback = discovery_cb
    _wizard_name_getter = wizard_getter

    try:
        _server_instance = HTTPServer(("127.0.0.1", port), _IngestHandler)
        t = threading.Thread(target=_server_instance.serve_forever, daemon=True)
        t.start()
        return True
    except OSError:
        # Port already in use — fail silently, just won't have live mode
        return False


def stop():
    global _server_instance
    if _server_instance:
        _server_instance.shutdown()
        _server_instance = None


def is_running():
    return _server_instance is not None


def get_last_contact():
    return _last_contact
