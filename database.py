import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "siege.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS defenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            monster1 TEXT NOT NULL,
            monster2 TEXT,
            monster3 TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS offenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            monster1 TEXT NOT NULL,
            monster2 TEXT,
            monster3 TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            defense_id INTEGER NOT NULL,
            offense_id INTEGER NOT NULL,
            result TEXT NOT NULL,
            guild_name TEXT,
            battle_date TEXT DEFAULT (datetime('now','localtime')),
            notes TEXT,
            FOREIGN KEY(defense_id) REFERENCES defenses(id),
            FOREIGN KEY(offense_id) REFERENCES offenses(id)
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS guild_cache (
            guild_id INTEGER PRIMARY KEY,
            guild_name TEXT
        );
    """)
    
    # ── Migration: Move label from defenses to battles.guild_name
    try:
        c.execute("SELECT guild_name FROM battles LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE battles ADD COLUMN guild_name TEXT")
        c.execute("""
            UPDATE battles 
            SET guild_name = (SELECT label FROM defenses WHERE defenses.id = battles.defense_id)
        """)
    
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
    conn.commit(); conn.close()

def save_guild_name(guild_id, guild_name):
    if not guild_id or not guild_name or guild_name == "Unknown": return
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO guild_cache (guild_id, guild_name) VALUES (?,?)", (guild_id, guild_name))
    conn.commit(); conn.close()

def get_guild_name(guild_id):
    if not guild_id: return "Unknown"
    conn = get_conn()
    row = conn.execute("SELECT guild_name FROM guild_cache WHERE guild_id=?", (guild_id,)).fetchone()
    conn.close()
    return row["guild_name"] if row else "Unknown"

# ── Defenses ──────────────────────────────────────────────
def add_defense(label, m1, m2, m3, notes):
    conn = get_conn()
    conn.execute(
        "INSERT INTO defenses (label,monster1,monster2,monster3,notes) VALUES (?,?,?,?,?)",
        (label, m1, m2, m3, notes)
    )
    conn.commit(); conn.close()

def get_defenses():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM defenses ORDER BY id DESC").fetchall()
    conn.close(); return rows

def delete_defense(def_id):
    conn = get_conn()
    conn.execute("DELETE FROM battles WHERE defense_id=?", (def_id,))
    conn.execute("DELETE FROM defenses WHERE id=?", (def_id,))
    conn.commit(); conn.close()

def update_defense(def_id, label, m1, m2, m3, notes):
    conn = get_conn()
    conn.execute(
        "UPDATE defenses SET label=?, monster1=?, monster2=?, monster3=?, notes=? WHERE id=?",
        (label, m1, m2, m3, notes, def_id)
    )
    conn.commit(); conn.close()

def clear_defenses():
    conn = get_conn()
    conn.execute("DELETE FROM battles")
    conn.execute("DELETE FROM defenses")
    conn.commit(); conn.close()

# ── Offenses ──────────────────────────────────────────────
def add_offense(label, m1, m2, m3, notes):
    conn = get_conn()
    conn.execute(
        "INSERT INTO offenses (label,monster1,monster2,monster3,notes) VALUES (?,?,?,?,?)",
        (label, m1, m2, m3, notes)
    )
    conn.commit(); conn.close()

def get_offenses():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM offenses ORDER BY id DESC").fetchall()
    conn.close(); return rows

def delete_offense(off_id):
    conn = get_conn()
    conn.execute("DELETE FROM battles WHERE offense_id=?", (off_id,))
    conn.execute("DELETE FROM offenses WHERE id=?", (off_id,))
    conn.commit(); conn.close()

def update_offense(off_id, label, m1, m2, m3, notes):
    conn = get_conn()
    conn.execute(
        "UPDATE offenses SET label=?, monster1=?, monster2=?, monster3=?, notes=? WHERE id=?",
        (label, m1, m2, m3, notes, off_id)
    )
    conn.commit(); conn.close()

def clear_offenses():
    conn = get_conn()
    conn.execute("DELETE FROM battles")
    conn.execute("DELETE FROM offenses")
    conn.commit(); conn.close()

# ── Battles ───────────────────────────────────────────────
def add_battle(def_id, off_id, result, guild_name, notes):
    conn = get_conn()
    conn.execute(
        "INSERT INTO battles (defense_id,offense_id,result,guild_name,notes) VALUES (?,?,?,?,?)",
        (def_id, off_id, result, guild_name, notes)
    )
    conn.commit(); conn.close()

def get_battles():
    conn = get_conn()
    rows = conn.execute("""
        SELECT b.*, 
               d.monster1||COALESCE(' / '||d.monster2,'')||COALESCE(' / '||d.monster3,'') as defense_str,
               o.monster1||COALESCE(' / '||o.monster2,'')||COALESCE(' / '||o.monster3,'') as offense_str,
               d.label as def_label, o.label as off_label
        FROM battles b
        JOIN defenses d ON b.defense_id = d.id
        JOIN offenses o ON b.offense_id = o.id
        ORDER BY b.battle_date DESC
    """).fetchall()
    conn.close(); return rows

def clear_battles():
    conn = get_conn()
    conn.execute("DELETE FROM battles")
    conn.commit(); conn.close()

def delete_battle(battle_id):
    conn = get_conn()
    conn.execute("DELETE FROM battles WHERE id=?", (battle_id,))
    conn.commit(); conn.close()

def update_battle_guild(battle_id, guild_name):
    conn = get_conn()
    conn.execute("UPDATE battles SET guild_name=? WHERE id=?", (guild_name, battle_id))
    conn.commit(); conn.close()

# ── Stats ─────────────────────────────────────────────────
def get_defense_stats():
    conn = get_conn()
    rows = conn.execute("""
        SELECT d.id,
               COALESCE(NULLIF(b.guild_name, ''), NULLIF(d.label, ''), 'Unknown') AS label,
               IFNULL(d.monster1, 'Unknown') || 
               CASE WHEN d.monster2 != '' THEN ' / ' || d.monster2 ELSE '' END ||
               CASE WHEN d.monster3 != '' THEN ' / ' || d.monster3 ELSE '' END AS comp,
               COUNT(b.id) AS total,
               SUM(CASE WHEN b.result='Win' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN b.result='Loss' THEN 1 ELSE 0 END) AS losses,
               MAX(b.battle_date) AS last_seen,
               (SELECT COUNT(*) FROM battles b2 JOIN defenses d2 ON b2.defense_id=d2.id 
                WHERE d2.monster1=d.monster1 AND d2.monster2=d.monster2 AND d2.monster3=d.monster3) AS g_total,
               (SELECT SUM(CASE WHEN b2.result='Win' THEN 1 ELSE 0 END) FROM battles b2 JOIN defenses d2 ON b2.defense_id=d2.id 
                WHERE d2.monster1=d.monster1 AND d2.monster2=d.monster2 AND d2.monster3=d.monster3) AS g_wins
        FROM defenses d
        LEFT JOIN battles b ON d.id=b.defense_id
        GROUP BY d.id, d.monster1, d.monster2, d.monster3, label
        ORDER BY total DESC, last_seen DESC
    """).fetchall()
    conn.close(); return rows

def get_offense_stats():
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.id, o.label as name,
               o.monster1||COALESCE(' / '||o.monster2,'')||COALESCE(' / '||o.monster3,'') as comp,
               COUNT(b.id) as total,
               SUM(CASE WHEN b.result='Win' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN b.result='Loss' THEN 1 ELSE 0 END) as losses
        FROM offenses o
        LEFT JOIN battles b ON o.id = b.offense_id
        GROUP BY o.id
        ORDER BY total DESC
    """).fetchall()
    conn.close(); return rows

def backup_db():
    import shutil
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, DB_PATH + ".bak")
