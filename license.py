"""
license.py — Self-validating beta license key system.

Key format:  SDBT-XXXX-XXXX-XXXX-CHCK
  - Prefix:     SDBT  (Siege Database Beta)
  - Parts 1-3:  4 random alphanumeric chars each
  - Checksum:   4-char HMAC derived from parts + secret

Keys are validated locally without a server.
Only the keygen.py script (kept private) can produce valid keys.
"""

import hashlib
import os

# ── Internal secret — reconstructed at runtime to prevent string scanning ──
def _get_s():
    # "SiegeDB::Evan::2026::beta::v2"
    bits = [83, 105, 101, 103, 101, 68, 66, 58, 58, 69, 118, 97, 110, 58, 58, 50, 48, 50, 54, 58, 58, 98, 101, 116, 97, 58, 58, 118, 50]
    return "".join(chr(b) for b in bits)

_SECRET = _get_s()
_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".license")


# ── Key validation ────────────────────────────────────────

def _checksum(parts: list[str]) -> str:
    """Derive 4-char checksum from the 3 key parts."""
    payload = _SECRET + "".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()[:4].upper()


def validate_key(key: str) -> bool:
    """Return True if the key has a valid structure and checksum."""
    key = key.strip().upper().replace(" ", "")
    segments = key.split("-")
    if len(segments) != 5:
        return False
    prefix, *parts, chk = segments
    if prefix != "SDBT":
        return False
    if any(len(p) != 4 for p in parts) or len(chk) != 4:
        return False
    return _checksum(parts) == chk


# ── Persistent storage ────────────────────────────────────

def load_saved_key() -> str | None:
    """Return the saved license key if it exists and is still valid."""
    try:
        with open(_KEY_FILE, "r") as f:
            key = f.read().strip()
        return key if validate_key(key) else None
    except FileNotFoundError:
        return None


def save_key(key: str):
    """Persist a validated key to disk."""
    with open(_KEY_FILE, "w") as f:
        f.write(key.strip().upper())


def is_licensed() -> bool:
    """Quick check — True if a valid key is already saved."""
    return load_saved_key() is not None
