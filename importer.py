"""
importer.py — imports siege data from Summoners War Exporter JSON files
and SWGTPersonalLogger battle log files into the Siege Database.
"""

import json
import os
import urllib.request
import urllib.error
import database as db

CACHE_FILE = os.path.join(os.path.dirname(__file__), "monster_names.json")
SWEX_FILES_PATH = r"C:\Users\Evan\Desktop\Summoners War Exporter Files"
SWARFARM_URL = "https://swarfarm.com/api/v2/monsters/?fields=com2us_id,name&page_size=2000&ordering=com2us_id"


# ── Monster name lookup ───────────────────────────────────

def load_monster_cache() -> dict:
    """Load cached unit_master_id → name mapping from disk."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_monster_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def fetch_monster_names() -> dict:
    """Fetch monster name lookup from swarfarm API (paginated). Returns {master_id: name}."""
    result = {}
    url = SWARFARM_URL
    while url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SiegeDB/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for m in data.get("results", []):
                if m.get("com2us_id"):
                    result[str(m["com2us_id"])] = m["name"]
            url = data.get("next")
        except Exception as e:
            break
    return result


def get_monster_names(force_refresh=False) -> dict:
    """Return monster name cache, refreshing from API if needed."""
    cache = load_monster_cache()
    if not cache or force_refresh:
        fresh = fetch_monster_names()
        if fresh:
            cache = fresh
            save_monster_cache(cache)
    return cache


def monster_name(master_id, names: dict) -> str:
    """Resolve unit_master_id to a display name."""
    if not master_id:
        return ""
    return names.get(str(master_id), f"[{master_id}]")


# ── SWEX JSON → My Offenses ───────────────────────────────

def import_offenses_from_swex(json_path: str) -> tuple[int, int]:
    """
    Parse an SWEX account JSON and import deck_type=22 (siege decks)
    as My Offenses. Returns (imported_count, skipped_count).
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    names = get_monster_names()

    # Build unit_id → unit_master_id map
    uid_map = {u["unit_id"]: u["unit_master_id"] for u in data.get("unit_list", [])}

    # Get existing offenses to skip duplicates (match on monster comp)
    existing = set()
    for row in db.get_offenses():
        key = (row["monster1"] or "", row["monster2"] or "", row["monster3"] or "")
        existing.add(key)

    siege_decks = [d for d in data.get("deck_list", []) if d["deck_type"] == 22]
    imported, skipped = 0, 0

    for i, deck in enumerate(siege_decks, 1):
        unit_ids = [uid for uid in deck.get("unit_id_list", []) if uid][:3]
        master_ids = [uid_map.get(uid) for uid in unit_ids]
        mon_names = [monster_name(mid, names) for mid in master_ids]
        # Pad to 3
        while len(mon_names) < 3:
            mon_names.append("")

        m1, m2, m3 = mon_names[0], mon_names[1], mon_names[2]
        key = (m1, m2, m3)
        if key in existing or not m1:
            skipped += 1
            continue

        label = f"Siege Deck {i}"
        db.add_offense(label, m1, m2, m3, "Imported from SWEX")
        existing.add(key)
        imported += 1

    return imported, skipped


# ── SWGTPersonalLogger battle files → Battles ────────────

def import_battles_from_logs(log_dir: str = SWEX_FILES_PATH) -> tuple[int, int]:
    """
    Scan the SWEX files directory for SWGTPersonalLogger battle JSON files
    and import them into the battles table.
    Files saved by the plugin look like:
      SWGTPersonalLogger-3MDC-0-3MDCBattleLog-<timestamp>.json
    with fields: defense.units, counter.units, win_lose (1=win, 0=loss)

    Returns (imported_count, skipped_count).
    """
    if not os.path.isdir(log_dir):
        return 0, 0

    names = get_monster_names()

    # Collect all log files
    log_files = [
        f for f in os.listdir(log_dir)
        if f.startswith("SWGTPersonalLogger") and f.endswith(".json")
        and "3MDCBattleLog" in f
    ]

    if not log_files:
        return 0, 0

    # Build lookup maps for existing defenses and offenses by monster comp
    def_by_comp = {}
    for row in db.get_defenses():
        key = tuple(sorted([row["monster1"] or "", row["monster2"] or "", row["monster3"] or ""]))
        def_by_comp[key] = row["id"]

    off_by_comp = {}
    for row in db.get_offenses():
        key = tuple(sorted([row["monster1"] or "", row["monster2"] or "", row["monster3"] or ""]))
        off_by_comp[key] = row["id"]

    imported, skipped = 0, 0
    
    # Get list of already imported filenames from battle notes to prevent duplicates
    existing_battles = db.get_battles()
    imported_fnames = set()
    for b in existing_battles:
        notes = b.get("notes") or ""
        if "Auto-imported from " in notes:
            fname = notes.replace("Auto-imported from ", "").strip()
            imported_fnames.add(fname)

    for fname in log_files:
        if fname in imported_fnames:
            skipped += 1
            continue
            
        fpath = os.path.join(log_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                battle = json.load(f)

            if battle.get("battleType") not in ("Siege", "SiegeTest"):
                skipped += 1
                continue

            def_units = battle.get("defense", {}).get("units", [])
            off_units = battle.get("counter", {}).get("units", [])
            win_lose = battle.get("win_lose")  # 1 = win, 0 = loss

            if len(def_units) < 3 or not off_units or win_lose is None:
                skipped += 1
                continue

            # Resolve names
            def_names = [monster_name(mid, names) for mid in def_units[:3]]
            off_names = [monster_name(mid, names) for mid in off_units[:3]]
            while len(def_names) < 3: def_names.append("")
            while len(off_names) < 3: off_names.append("")

            # Get or create defense
            def_key = tuple(sorted(def_names))
            if def_key not in def_by_comp:
                db.add_defense("", def_names[0], def_names[1], def_names[2], "Auto-imported")
                def_id = db.get_defenses()[0]["id"]
                def_by_comp[def_key] = def_id
            def_id = def_by_comp[def_key]

            # Get or create offense
            off_key = tuple(sorted(off_names))
            if off_key not in off_by_comp:
                db.add_offense("Auto-imported", off_names[0], off_names[1], off_names[2], "Auto-imported")
                off_id = db.get_offenses()[0]["id"]
                off_by_comp[off_key] = off_id
            off_id = off_by_comp[off_key]

            result = "Win" if win_lose == 1 else "Loss"
            guild = battle.get("guild_name") or "Unknown"
            db.add_battle(def_id, off_id, result, guild, f"Auto-imported from {fname}")
            imported += 1

        except Exception:
            skipped += 1

    return imported, skipped


# ── Combined import ───────────────────────────────────────

def import_battles_from_siege_logs(log_dir: str = SWEX_FILES_PATH, my_wizard_name: str = "Delirious") -> tuple[int, int]:
    """
    Parse SWGT-GetGuildSiegeBattleLog-*.json files and import YOUR battles.
    These files contain nested log_list entries per siege match with:
      - wizard_name / opp_guild_name
      - win_lose (1=win, 2=loss)
      - view_battle_deck_info: [[my monster IDs], [enemy monster IDs]]

    Returns (imported_count, skipped_count).
    """
    if not os.path.isdir(log_dir):
        return 0, 0

    names = get_monster_names()

    log_files = sorted([
        f for f in os.listdir(log_dir)
        if f.startswith("SWGT-GetGuildSiegeBattleLog") and f.endswith(".json")
    ])

    if not log_files:
        return 0, 0

    # Build lookup maps
    def_by_comp = {}
    for row in db.get_defenses():
        key = tuple(sorted([row["monster1"] or "", row["monster2"] or "", row["monster3"] or ""]))
        def_by_comp[key] = row["id"]

    off_by_comp = {}
    for row in db.get_offenses():
        key = tuple(sorted([row["monster1"] or "", row["monster2"] or "", row["monster3"] or ""]))
        off_by_comp[key] = row["id"]

    # Collect already-imported log_ids to prevent duplicates
    existing_battles = db.get_battles()
    imported_log_ids = set()
    # Also build a lookup so we can UPDATE guild on old records imported without proper guild
    # Key: (def_id, off_id, result, date_prefix) -> battle_id
    existing_battle_map = {}
    for b in existing_battles:
        notes = b["notes"] or ""
        if notes.startswith("siege_log_id:"):
            imported_log_ids.add(notes.split(":")[1].strip())
        # Build a fuzzy match key for guild correction
        date_prefix = (b["battle_date"] or "")[:10]  # YYYY-MM-DD
        key = (b["defense_id"] if "defense_id" in b.keys() else None,
               b["result"], date_prefix)
        existing_battle_map[key] = b["id"]

    imported, skipped = 0, 0

    for fname in log_files:
        fpath = os.path.join(log_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # log_list is a list of match objects, each with battle_log_list
            for match in data.get("log_list", []):
                for entry in match.get("battle_log_list", []):
                    # Only import YOUR attacks
                    if entry.get("wizard_name", "").lower() != my_wizard_name.lower():
                        skipped += 1
                        continue

                    log_id = str(entry.get("log_id", ""))
                    if log_id in imported_log_ids:
                        skipped += 1
                        continue

                    deck_info = entry.get("view_battle_deck_info", [])
                    if len(deck_info) < 2:
                        skipped += 1
                        continue

                    my_ids  = deck_info[0][:3]   # attacker = your team
                    opp_ids = deck_info[1][:3]    # defender = enemy team

                    my_names  = [monster_name(mid, names) for mid in my_ids]
                    opp_names = [monster_name(mid, names) for mid in opp_ids]
                    while len(my_names)  < 3: my_names.append("")
                    while len(opp_names) < 3: opp_names.append("")

                    # Get or create offense (your team)
                    off_key = tuple(sorted(my_names))
                    if off_key not in off_by_comp:
                        db.add_offense("Auto-imported", my_names[0], my_names[1], my_names[2], "Auto-imported from siege log")
                        off_id = db.get_offenses()[0]["id"]
                        off_by_comp[off_key] = off_id
                    off_id = off_by_comp[off_key]

                    # Get or create defense (enemy team)
                    def_key = tuple(sorted(opp_names))
                    if def_key not in def_by_comp:
                        db.add_defense("", opp_names[0], opp_names[1], opp_names[2], "Auto-imported from siege log")
                        def_id = db.get_defenses()[0]["id"]
                        def_by_comp[def_key] = def_id
                    def_id = def_by_comp[def_key]

                    result = "Win" if entry.get("win_lose") == 1 else "Loss"
                    opp_guild = entry.get("opp_guild_name", "Unknown").strip()

                    # Convert log timestamp to date string for matching
                    import datetime
                    ts = entry.get("log_timestamp", 0)
                    log_date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""

                    # Check if this battle already exists (fuzzy match on def+result+date)
                    match_key = (def_id, result, log_date)
                    if log_id in imported_log_ids:
                        # Already imported via siege_log_id — just correct the guild if it's stale
                        if match_key in existing_battle_map:
                            db.update_battle_guild(existing_battle_map[match_key], opp_guild)
                        skipped += 1
                        continue

                    # New battle — insert it
                    db.add_battle(def_id, off_id, result, opp_guild, f"siege_log_id:{log_id}")
                    imported_log_ids.add(log_id)
                    imported += 1

        except Exception:
            skipped += 1

    return imported, skipped


def get_or_create_defense(monster_names, note="Auto-imported"):
    """Check if a defense exists, if not create it. Returns def_id."""
    def_by_comp = {}
    for row in db.get_defenses():
        key = tuple(sorted([row["monster1"] or "", row["monster2"] or "", row["monster3"] or ""]))
        def_by_comp[key] = row["id"]

    def_key = tuple(sorted(monster_names))
    if def_key not in def_by_comp:
        db.add_defense("", monster_names[0], monster_names[1], monster_names[2], note)
        return db.get_defenses()[0]["id"]
    return def_by_comp[def_key]


def update_guild_cache(data):
    # Scan for guild_info_list in various packets
    guilds = data.get("guild_info_list") or data.get("guild_info")
    if not guilds: return
    
    if isinstance(guilds, dict): guilds = [guilds]
    if not isinstance(guilds, list): return
    
    for g in guilds:
        if not isinstance(g, dict): continue
        gid = g.get("guild_id")
        name = g.get("guild_name")
        if gid and name:
            db.save_guild_name(gid, name)

def process_discovery(cmd_type: str, data: dict) -> int:
    """Handle non-battle data like tower clicks or rankings."""
    if not data: return 0
    
    names = get_monster_names()
    count = 0

    # ── Update Guild Phone Book ──
    update_guild_cache(data)

    # ── Tower Click (Handle Grouped Monsters)
    if cmd_type in ["GetGuildSiegeBaseInfo", "GetGuildSiegeBaseDefenseUnitListPreset"]:
        # 1. Group loose units by deck_id
        raw_units = data.get("defense_unit_list", [])
        decks_map = {}
        for u in raw_units:
            did = u.get("deck_id")
            if did:
                if did not in decks_map: decks_map[did] = []
                decks_map[did].append(u)
        
        # 2. Try to find guild name from current packet or cache
        base = data.get("base_info", {})
        guild_id = base.get("guild_id")
        guild_name = db.get_guild_name(guild_id)

        # 3. Process each grouped deck
        for did, units in decks_map.items():
            m_ids = []
            # Sort by pos_id just in case
            units.sort(key=lambda x: x.get("pos_id", 0))
            for u in units:
                ui = u.get("unit_info", {})
                mid = ui.get("unit_master_id") or u.get("unit_master_id") or u.get("master_id")
                if mid: m_ids.append(mid)
            
            m_ids = m_ids[:3]
            m_names = [monster_name(mid, names) for mid in m_ids]
            while len(m_names) < 3: m_names.append("")
            
            if m_names[0]:
                get_or_create_defense(m_names, f"Discovered via {cmd_type} (Guild: {guild_name})")
                count += 1

    return count


def process_live_battle(entry: dict, wizard_name: str = "") -> dict:
    """
    Process a single battle_log_list entry sent in real-time by the SWEX plugin.
    ...
    """
    # Filter by wizard name if configured
    if wizard_name:
        entry_wiz = (entry.get("wizard_name") or "").strip().lower()
        if entry_wiz and entry_wiz != wizard_name.strip().lower():
            return {"status": "skipped", "reason": "wizard_name mismatch"}

    log_id = str(entry.get("log_id", ""))

    # Duplicate check
    if log_id:
        for b in db.get_battles():
            if (b["notes"] or "").startswith(f"siege_log_id:{log_id}"):
                return {"status": "duplicate"}

    deck_info = entry.get("view_battle_deck_info", [])
    if len(deck_info) < 2:
        return {"status": "skipped", "reason": "missing deck info"}

    my_ids  = deck_info[0][:3]   # attacker = your team
    opp_ids = deck_info[1][:3]   # defender = enemy team

    names = get_monster_names()
    my_names  = [monster_name(mid, names) for mid in my_ids]
    opp_names = [monster_name(mid, names) for mid in opp_ids]
    while len(my_names)  < 3: my_names.append("")
    while len(opp_names) < 3: opp_names.append("")

    if not my_names[0] or not opp_names[0]:
        return {"status": "skipped", "reason": "could not resolve monster names"}

    # Get or create offense (your team)
    off_by_comp = {}
    for row in db.get_offenses():
        key = tuple(sorted([row["monster1"] or "", row["monster2"] or "", row["monster3"] or ""]))
        off_by_comp[key] = row["id"]

    off_key = tuple(sorted(my_names))
    if off_key not in off_by_comp:
        db.add_offense("Auto-imported", my_names[0], my_names[1], my_names[2], "Auto-imported from live plugin")
        off_id = db.get_offenses()[0]["id"]
        off_by_comp[off_key] = off_id
    off_id = off_by_comp[off_key]

    # Update guild cache if we see guild info in the battle log
    update_guild_cache(entry)
    
    # Get or create defense (enemy team) using the helper
    def_id = get_or_create_defense(opp_names, "Auto-imported from live plugin")

    result    = "Win" if entry.get("win_lose") == 1 else "Loss"
    opp_guild = (entry.get("opp_guild_name") or "Unknown").strip()
    note      = f"siege_log_id:{log_id}" if log_id else "live-import"

    db.add_battle(def_id, off_id, result, opp_guild, note)
    return {"status": "ok", "defense": " / ".join(filter(None, opp_names)),
            "offense": " / ".join(filter(None, my_names)), "result": result}


def run_import(json_path: str = None, log_dir: str = SWEX_FILES_PATH, my_wizard_name: str = "Delirious") -> dict:
    """Run all available imports. Returns summary dict."""
    results = {}

    if json_path and os.path.exists(json_path):
        off_imp, off_skip = import_offenses_from_swex(json_path)
        results["offenses_imported"] = off_imp
        results["offenses_skipped"] = off_skip

    bat_imp, bat_skip = import_battles_from_logs(log_dir)
    results["battles_imported"] = bat_imp
    results["battles_skipped"] = bat_skip

    siege_imp, siege_skip = import_battles_from_siege_logs(log_dir, my_wizard_name)
    results["siege_battles_imported"] = siege_imp
    results["siege_battles_skipped"] = siege_skip

    return results
