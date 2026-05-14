"""
ai_advisor.py — queries local Ollama for siege counter suggestions
and full siege battle planning using the player's win/loss database.
"""
import json
import urllib.request
import urllib.error

OLLAMA_BASE = "http://localhost:11434"

SYSTEM_PROMPT = """You are an expert Summoners War siege battle advisor.

SIEGE BASICS:
- Guild Siege is 3v3 content where your team of 3 monsters attacks an enemy defense of 3 monsters.
- Turn order is determined by Speed stat — fastest monster goes first.
- Winning requires either killing all 3 enemy monsters or having more HP remaining when time expires.
- Each offense team can only be used ONCE per siege wave. You must assign different teams to different nodes.

KEY ROLES:
- Nuker/DPS: High damage dealers (e.g. Lushen, Tablo, Hwa, Perna, Camilla, Ritesh)
- Cleanser: Removes harmful effects from allies (e.g. Chloe, Veromos, Megan, Triton)
- Controller: Applies crowd control — stuns, slow, sleep, provoke (e.g. Baretta, Colleen, Belladeon)
- Sustain/Healer: Keeps team alive (e.g. Chloe, Praha, Mihail, Shimitae)
- Stripper: Removes beneficial effects from enemies (e.g. Lushen, Galleon, Ritesh, Luer)
- Buffer: Boosts ally stats — ATK, DEF, SPD (e.g. Galleon, Bastet, Loren, Charite)
- Tank/Shield: High HP/DEF units that absorb damage

COUNTER PRINCIPLES:
- Beat sustain defenses → bring strip + high damage
- Beat nuker defenses → bring cleanser or immunity (Chloe, Vero)
- Beat controller defenses → bring immunity team or cleanser
- Beat speed-first teams → match or exceed speed, or bring stunners
- Defense has a healer → must out-strip or out-damage the heals
- Violent/revenge rune defenses → bring enough damage to burst before they proc

When asked about a specific defense, suggest 2-3 concrete offense teams of 3 monsters each.
Format each suggestion as: Monster 1 / Monster 2 / Monster 3 — [reason]
"""

PLANNER_PROMPT = """You are an expert Summoners War siege BATTLE PLANNER.

Your job is to assign the player's available offense teams to enemy defense nodes to maximize the overall probability of winning the siege wave.

CRITICAL RULES:
1. Each offense team can only be used ONCE. Do not assign the same team to multiple nodes.
2. Consider the player's historical win rates when assigning — prefer high-winrate matchups.
3. Save strong/flexible teams for harder defenses.
4. If the player has fewer offense teams than defense nodes, prioritize the most dangerous defenses.
5. For each assignment, briefly explain WHY this team counters that specific defense.

OUTPUT FORMAT (use exactly this format):
NODE 1: [defense comp]
→ ASSIGN: [offense team name] (Monster1 / Monster2 / Monster3)
→ WHY: [brief reasoning]
→ CONFIDENCE: [High/Medium/Low] — [one sentence on risk]

NODE 2: ...

SUMMARY: [1-2 sentences on overall strategy and which nodes are risky]
"""


def list_models() -> list[str]:
    """Return list of available Ollama model names."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _call_ollama(model: str, system: str, user_msg: str, temperature: float = 0.4) -> str:
    """Core Ollama chat call. Returns response text or error string."""
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg},
        ],
        "options": {"temperature": temperature},
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
        return result["message"]["content"].strip()
    except urllib.error.URLError:
        return "❌ Could not connect to Ollama. Make sure it is running (ollama serve)."
    except Exception as e:
        return f"❌ Error: {e}"


def ask_ollama(model: str, defense_comp: str, history_text: str,
               extra_notes: str = "") -> str:
    """Single-defense counter suggestion."""
    history_section = (
        f"\nMY BATTLE HISTORY VS THIS DEFENSE:\n{history_text}"
        if history_text.strip() else
        "\nMY BATTLE HISTORY: No recorded battles against this defense yet."
    )
    notes_section = f"\nADDITIONAL NOTES FROM PLAYER: {extra_notes}" if extra_notes.strip() else ""

    user_msg = (
        f"I am facing this siege defense: {defense_comp}\n"
        f"{history_section}"
        f"{notes_section}\n\n"
        f"What are the best 2-3 offense teams I should use to beat this defense? "
        f"For each suggestion, explain briefly WHY it counters this specific defense."
    )
    return _call_ollama(model, SYSTEM_PROMPT, user_msg)


def plan_siege(model: str, defense_nodes: list[str],
               offense_teams: list[dict], extra_notes: str = "") -> str:
    """
    Full siege planner: assign offense teams to defense nodes optimally.

    defense_nodes: list of comp strings, e.g. ["Lushen / Galleon / Perna", ...]
    offense_teams: list of dicts with keys: label, comp, history_text
    """
    # Build defense block
    def_block = "\n".join(
        f"  Node {i+1}: {comp}" for i, comp in enumerate(defense_nodes)
    )

    # Build offense block with history
    off_lines = []
    for i, t in enumerate(offense_teams, 1):
        hist = f" | History: {t['history_text']}" if t.get("history_text") else " | History: none"
        off_lines.append(f"  Team {i}: {t['label']} ({t['comp']}){hist}")
    off_block = "\n".join(off_lines)

    notes_section = f"\nPLAYER NOTES: {extra_notes}" if extra_notes.strip() else ""

    user_msg = (
        f"ENEMY DEFENSE NODES:\n{def_block}\n\n"
        f"MY AVAILABLE OFFENSE TEAMS:\n{off_block}\n"
        f"{notes_section}\n\n"
        f"Assign my offense teams to the enemy nodes to maximize win probability. "
        f"Remember each team can only be used once."
    )
    return _call_ollama(model, PLANNER_PROMPT, user_msg, temperature=0.3)


def build_history_text(defense_id: int) -> str:
    """Readable summary of win/loss records vs a defense for AI context."""
    import database as db
    rows = db.get_offense_stats_for_defense(defense_id)
    if not rows:
        return ""
    lines = []
    for r in rows:
        wins = r["wins"] or 0
        total = r["total"] or 0
        losses = total - wins
        pct = int(wins / total * 100) if total else 0
        lines.append(
            f"  • {r['label'] or r['comp']} ({r['comp']}): "
            f"{wins}W / {losses}L ({pct}% winrate)"
        )
    return "\n".join(lines)


def build_offense_teams_for_planner() -> list[dict]:
    """Load all offenses from DB with their overall history for the planner prompt."""
    import database as db
    teams = []
    for r in db.get_offense_stats():
        comp = r["comp"]
        wins = r["wins"] or 0
        total = r["total"] or 0
        losses = total - wins
        pct = int(wins / total * 100) if total else 0
        hist = f"{wins}W/{losses}L ({pct}%)" if total else "no battles yet"
        teams.append({"label": r["label"] or comp, "comp": comp, "history_text": hist})
    return teams
