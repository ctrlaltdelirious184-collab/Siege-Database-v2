import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading
import database as db
import importer
import license as lic
import ingest_server

# ── Palette ───────────────────────────────────────────────
BG       = "#070b14"
SIDE     = "#0b0f1c"
PANEL    = "#0f1422"
CARD     = "#141929"
CARD2    = "#1a2035"
ACCENT   = "#7c3aed"
ACCENT_H = "#9461ff"
ACCENT2  = "#0891b2"
ACCENT2H = "#06b6d4"
WIN_CLR  = "#10b981"
WIN_H    = "#34d399"
LOSS_CLR = "#ef4444"
LOSS_H   = "#f87171"
FG       = "#e2e8ff"
FG2      = "#5c6b9e"
FG3      = "#252f50"
BORDER   = "#1a2444"
GOLD     = "#f59e0b"
FONT     = ("Segoe UI", 10)
FONT_B   = ("Segoe UI", 10, "bold")
FONT_H   = ("Segoe UI", 14, "bold")
ACCENT_BG = "#1e1b4b"
FONT_SM  = ("Segoe UI", 9)
FONT_LG  = ("Segoe UI", 13, "bold")

# ── Components ───────────────────────────────────────────

class DonutChart(tk.Canvas):
    def __init__(self, parent, size=80, bg=BG):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size
        self.bg = bg
        self.wins = 0
        self.total = 0
        self.cur_extent = 0
        self._anim_id = None

    def update_stats(self, wins, total):
        self.wins = wins
        self.total = total
        target_extent = (self.wins / self.total * 359.9) if total > 0 else 0
        self._animate(target_extent)

    def _animate(self, target):
        if self._anim_id: self.after_cancel(self._anim_id)
        diff = target - self.cur_extent
        if abs(diff) < 0.5:
            self.cur_extent = target
            self.draw()
            return
            
        self.cur_extent += diff * 0.15 # Smooth spring physics
        self.draw()
        self._anim_id = self.after(16, lambda: self._animate(target))

    def draw(self):
        self.delete("all")
        cx, cy = self.size / 2, self.size / 2
        r = (self.size / 2) - 6
        
        # Background ring (Dark track)
        self.create_oval(cx-r, cy-r, cx+r, cy+r, outline=CARD, width=10)
        
        if self.total > 0 or self.cur_extent > 1:
            # Win arc (Animated)
            self.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, extent=-self.cur_extent, 
                            outline=WIN_CLR, width=10, style="arc")
            
            # Percentage text
            pct = int((self.wins / self.total) * 100) if self.total > 0 else 0
            self.create_text(cx, cy, text=f"{pct}%", fill=FG, font=("Segoe UI", 11, "bold"))
        else:
            self.create_text(cx, cy, text="—", fill=FG2, font=("Segoe UI", 11, "bold"))

# ── Helpers ───────────────────────────────────────────────
_HOVER = {ACCENT: ACCENT_H, ACCENT2: ACCENT2H, WIN_CLR: WIN_H, LOSS_CLR: LOSS_H}

def styled_btn(parent, text, cmd, color=ACCENT, fg=FG, width=12):
    hover = _HOVER.get(color, _lighten(color))
    b = tk.Button(parent, text=text, command=cmd,
                  bg=color, fg=fg, font=FONT_B,
                  relief="flat", bd=0, padx=12, pady=7,
                  cursor="hand2", activebackground=hover, activeforeground=fg, width=width)
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=color))
    return b

def _lighten(hex_color):
    r,g,b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
    return "#{:02x}{:02x}{:02x}".format(min(r+25,255), min(g+25,255), min(b+25,255))

def sep(parent, vertical=False):
    """Thin separator line."""
    kw = dict(bg=BORDER)
    if vertical: return tk.Frame(parent, width=1, **kw)
    return tk.Frame(parent, height=1, **kw)

def lf(parent, text="", **kw):
    return tk.LabelFrame(parent, text=text, bg=PANEL, fg=FG2, font=FONT_SM,
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER, **kw)

def card(parent, accent_color=None, **kw):
    """Premium card frame with optional colored left accent bar."""
    outer = tk.Frame(parent, bg=accent_color or BORDER, padx=1 if accent_color else 0)
    inner = tk.Frame(outer, bg=CARD, **kw)
    inner.pack(fill="both", expand=True, padx=(2 if accent_color else 0), pady=0)
    outer._inner = inner
    return outer

def label(parent, text, font=FONT, fg=FG, **kw):
    return tk.Label(parent, text=text, bg=PANEL, fg=fg, font=font, **kw)

def entry(parent, width=28, bg=None):
    e = tk.Entry(parent, width=width, bg=bg or CARD2, fg=FG, font=FONT,
                 insertbackground=FG, relief="flat", bd=5)
    return e

def scrolled_tree(parent, cols, heights=15):
    frame = tk.Frame(parent, bg=BG, highlightthickness=1, highlightbackground=BORDER)
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Custom.Treeview",
                    background=CARD, foreground=FG, fieldbackground=CARD,
                    rowheight=34, font=FONT, borderwidth=0)
    style.configure("Custom.Treeview.Heading",
                    background=PANEL, foreground=ACCENT, font=("Segoe UI", 9, "bold"),
                    relief="flat", padding=8)
    style.map("Custom.Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", FG)])
    style.map("Custom.Treeview.Heading",
              background=[("active", CARD2)])
    tv = ttk.Treeview(frame, columns=cols, show="headings", style="Custom.Treeview", height=heights)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tv.tag_configure("alt", background=CARD2)
    return frame, tv

def winrate_str(wins, total):
    if total == 0: return "—"
    return f"{int(wins/total*100)}%  ({wins}W/{total-wins}L)"

def get_wr_tag(wins, total):
    if total == 0: return "win"
    rate = wins / total
    if rate >= 0.87: return "win"
    if rate >= 0.82: return "warn"
    return "crit"

# ── Search Entry (Google Style) ───────────────────────────
class SearchEntry(tk.Frame):
    def __init__(self, parent, values=None, width=32, placeholder="", on_selection=None):
        super().__init__(parent, bg=PANEL)
        self.all_values = values or []
        self._on_selection = on_selection
        
        # Main entry
        self.entry = entry(self, width=width)
        self.entry.pack(fill="x", expand=True)
        
        self.entry.bind("<KeyRelease>", self._on_keyrelease)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Down>", self._on_down_arrow)
        self.entry.bind("<Return>", self._on_enter)
        
        self.popup = None
        self.listbox = None

    def set_all_values(self, values):
        self.all_values = values
        if self.popup: self._update_listbox()

    def get(self):
        return self.entry.get().strip()

    def set(self, text):
        self.entry.delete(0, "end")
        self.entry.insert(0, text or "")

    def _show_popup(self):
        if self.popup: return
        self.popup = tk.Toplevel(self)
        self.popup.wm_overrideredirect(True)
        self.popup.configure(bg=BORDER)
        
        # Position exactly below entry
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        w = self.entry.winfo_width()
        self.popup.wm_geometry(f"{w}x180+{x}+{y}")
        
        self.listbox = tk.Listbox(self.popup, bg=CARD, fg=FG, font=FONT, 
                                  borderwidth=0, highlightthickness=0,
                                  selectbackground=ACCENT, activestyle="none")
        self.listbox.pack(fill="both", expand=True)
        
        # Bindings for the listbox
        self.listbox.bind("<Button-1>", lambda e: self.after(10, self._accept_selection))
        self.listbox.bind("<Return>", lambda e: self._accept_selection())

    def _update_listbox(self):
        query = self.entry.get().lower().strip()
        if not query:
            if self.popup: self.popup.destroy(); self.popup = None
            return
            
        # Token-based search: match if all words in query are present in the item
        tokens = query.split()
        matches = []
        for v in self.all_values:
            v_lower = v.lower()
            if all(t in v_lower for t in tokens):
                matches.append(v)
                
        if not matches:
            if self.popup: self.popup.destroy(); self.popup = None
            return
            
        self._show_popup()
        self.listbox.delete(0, "end")
        for m in matches:
            self.listbox.insert("end", m)

    def _on_keyrelease(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        self._update_listbox()

    def _on_down_arrow(self, event):
        if self.listbox:
            self.listbox.focus_set()
            self.listbox.selection_set(0)

    def _on_enter(self, event):
        if self.popup:
            self._accept_selection()
        if self._on_selection:
            self._on_selection()

    def _on_focus_out(self, event):
        # Small delay to allow clicking the listbox
        self.after(200, self._hide_popup_if_needed)

    def _hide_popup_if_needed(self):
        if not self.popup: return
        # Don't hide if listbox still has focus
        try:
            if self.focus_get() != self.listbox:
                self.popup.destroy()
                self.popup = None
        except: pass

    def _accept_selection(self):
        if not self.listbox: return
        sel = self.listbox.curselection()
        if sel:
            val = self.listbox.get(sel[0])
            self.set(val)
            if self._on_selection: self._on_selection()
        if self.popup:
            self.popup.destroy()
            self.popup = None
        self.entry.focus_set()

# ── Monster Entry Group ───────────────────────────────────
class MonsterGroup(tk.Frame):
    def __init__(self, parent, show_label=True, label_text="Guild"):
        super().__init__(parent, bg=PANEL)
        row = 0
        if show_label:
            tk.Label(self, text=label_text, bg=PANEL, fg=FG2, font=FONT_SM).grid(row=row, column=0, sticky="w")
            self.lbl = entry(self, 28); self.lbl.grid(row=row+1, column=0, columnspan=3, sticky="ew", pady=(0,6))
            row += 2
        else:
            self.lbl = None
        for i, name in enumerate(["Monster 1 *", "Monster 2", "Monster 3"]):
            tk.Label(self, text=name, bg=PANEL, fg=FG2, font=FONT_SM).grid(row=row, column=i, sticky="w", padx=(0,4))
        self.m = []
        for i in range(3):
            e = entry(self, 14); e.grid(row=row+1, column=i, padx=(0,4), sticky="ew")
            self.m.append(e)
        tk.Label(self, text="Notes", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=row+2, column=0, sticky="w", pady=(8,0))
        self.notes = entry(self, 42)
        self.notes.grid(row=row+3, column=0, columnspan=3, sticky="ew")
        self.columnconfigure(0, weight=1); self.columnconfigure(1, weight=1); self.columnconfigure(2, weight=1)

    def get(self):
        label = self.lbl.get().strip() if self.lbl else ""
        m = [x.get().strip() for x in self.m]
        return label, m[0], m[1], m[2], self.notes.get().strip()

    def set(self, label, m1, m2, m3, notes):
        if self.lbl: self.lbl.delete(0,"end"); self.lbl.insert(0, label or "")
        for e, v in zip(self.m, [m1,m2,m3]):
            e.delete(0,"end"); e.insert(0, v or "")
        self.notes.delete(0,"end"); self.notes.insert(0, notes or "")

    def clear(self):
        self.set("","","","","")

# ── Dialog for add/edit ───────────────────────────────────
class RecordDialog(tk.Toplevel):
    def __init__(self, parent, title, show_label=True, label_text="Guild", initial=None):
        super().__init__(parent)
        self.title(title); self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")
        tk.Label(self, text=title, bg=BG, fg=FG, font=FONT_H).pack(padx=24, pady=(16,4))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(0,8))
        self.mg = MonsterGroup(self, show_label=show_label, label_text=label_text)
        self.mg.pack(padx=24, pady=8, fill="x")
        
        # Tier Selector
        self.tier_var = tk.StringVar(value=initial[5] if (initial and len(initial) > 5) else "5*")
        tf = tk.Frame(self, bg=BG); tf.pack(fill="x", padx=24, pady=4)
        tk.Label(tf, text="Tier:", bg=BG, fg=FG2, font=FONT_SM).pack(side="left")
        for t in ["5*", "4*"]:
            tk.Radiobutton(tf, text=t, variable=self.tier_var, value=t,
                           bg=BG, fg=FG, selectcolor=SIDE, activebackground=BG,
                           activeforeground=FG, font=FONT_SM).pack(side="left", padx=10)

        if initial: self.mg.set(*initial[:5])
        bf = tk.Frame(self, bg=BG)
        bf.pack(pady=(8,20), padx=24, fill="x")
        styled_btn(bf, "Save", self._save, ACCENT).pack(side="right", padx=4)
        styled_btn(bf, "Cancel", self.destroy, CARD).pack(side="right", padx=4)
        self.grab_set(); self.wait_window()

    def _save(self):
        lbl, m1, m2, m3, notes = self.mg.get()
        if not m1:
            messagebox.showwarning("Missing", "Monster 1 is required.", parent=self); return
        self.result = (lbl, m1, m2, m3, notes, self.tier_var.get())
        self.destroy()


# ── Quick Battle Dialog ───────────────────────────────────
class QuickBattleDialog(tk.Toplevel):
    """Lightweight dialog to record a battle against a pre-selected defense."""
    def __init__(self, parent, defense_id, offenses):
        super().__init__(parent)
        self.title("Record Battle")
        self.configure(bg=BG)
        self.resizable(False, False)
        

        self.result = None
        tk.Frame(self, bg=WIN_CLR, height=3).pack(fill="x")
        tk.Label(self, text="Record Battle Result", bg=BG, fg=FG, font=FONT_H).pack(padx=24, pady=(16,4))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(0,8))

        f = tk.Frame(self, bg=BG); f.pack(padx=24, pady=8, fill="x")

        # Offense picker
        tk.Label(f, text="My Offense", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=0, column=0, sticky="w")
        self._off_map = {f"[{r['id']}] {r['label']} — {r['monster1']}{(' / '+r['monster2']) if r['monster2'] else ''}{(' / '+r['monster3']) if r['monster3'] else ''}": r['id'] for r in offenses}
        self._off_var = tk.StringVar(value=list(self._off_map.keys())[0])
        self.off_search = SearchEntry(f, values=list(self._off_map.keys()), width=40)
        self.off_search.grid(row=1, column=0, padx=(0,16), pady=(2,8))
        self.off_search.set(self._off_var.get())

        # Result
        tk.Label(f, text="Result", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=0, column=1, sticky="w")
        self._result_var = tk.StringVar(value="Win")
        rf = tk.Frame(f, bg=PANEL); rf.grid(row=1, column=1, padx=(0,16))
        for v in ("Win", "Loss"):
            tk.Radiobutton(rf, text=v, variable=self._result_var, value=v,
                           bg=PANEL, fg=WIN_CLR if v == "Win" else LOSS_CLR,
                           selectcolor=CARD, font=FONT_B, activebackground=PANEL).pack(side="left", padx=6)

        # Guild
        tk.Label(f, text="Guild Name", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=2, column=1, sticky="w", pady=(4,0))
        self._guild_e = entry(f, 20)
        self._guild_e.grid(row=3, column=1, sticky="ew", padx=(0,16))

        # Notes
        tk.Label(f, text="Notes (optional)", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=4, column=0, sticky="w", pady=(4,0))
        self._notes = entry(f, 42)
        self._notes.grid(row=5, column=0, columnspan=2, sticky="ew")

        bf = tk.Frame(self, bg=PANEL); bf.pack(pady=(4,16), padx=24, fill="x")
        styled_btn(bf, "Record", self._save, ACCENT).pack(side="right", padx=4)
        styled_btn(bf, "Cancel", self.destroy, CARD).pack(side="right", padx=4)
        self.grab_set(); self.wait_window()

    def _save(self):
        off_key = self.off_search.get()
        if not off_key or off_key not in self._off_map:
            messagebox.showwarning("Invalid", "Please select a valid offense team from the list.", parent=self)
            return
        self.result = (self._off_map[off_key], self._result_var.get(), self._guild_e.get().strip(), self._notes.get().strip())
        self.destroy()

# ── Defenses Tab ──────────────────────────────────────────
class DefensesTab(tk.Frame):
    def __init__(self, parent, on_change):
        super().__init__(parent, bg=BG)
        self.on_change = on_change
        self._all_rows = []  # cached full list for filtering

        # ── Header
        tk.Label(self, text="⚔  Enemy Defenses", bg=BG, fg=FG, font=FONT_H).pack(anchor="w", padx=20, pady=(16,4))
        tk.Label(self, text="Track the defense compositions you face in Siege.", bg=BG, fg=FG2, font=FONT_SM).pack(anchor="w", padx=20)

        # ── Search + buttons row
        top = tk.Frame(self, bg=BG); top.pack(fill="x", padx=20, pady=10)
        tk.Label(top, text="🔍", bg=BG, fg=FG2, font=("Segoe UI", 12)).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filter())
        search_e = tk.Entry(top, textvariable=self._search_var, width=28,
                            bg=CARD, fg=FG, font=FONT, insertbackground=FG,
                            relief="flat", bd=4)
        search_e.pack(side="left", padx=(4, 16))
        
        # Tier Filter
        self._tier_var = tk.StringVar(value="All")
        for t in ["All", "5*", "4*"]:
            rb = tk.Radiobutton(top, text=t, variable=self._tier_var, value=t,
                                command=self._apply_filter, bg=CARD, fg=FG,
                                selectcolor=SIDE, activebackground=ACCENT,
                                activeforeground=FG, font=("Segoe UI", 8, "bold"), 
                                indicatoron=False, width=6,
                                padx=10, pady=2, bd=1, relief="flat")
            rb.pack(side="left", padx=1)

        tk.Frame(top, width=20, bg=BG).pack(side="left") # Spacer
        
        styled_btn(top, "+ Add Defense", self._add, ACCENT).pack(side="left", padx=(0,8))
        styled_btn(top, "✏ Edit", self._edit, CARD).pack(side="left", padx=(0,8))
        styled_btn(top, "🗑 Delete", self._delete, "#6b2f2f").pack(side="left", padx=(0,8))
        styled_btn(top, "🗑 Clear All", self._clear_all, "#4a1c1c", width=12).pack(side="left", padx=(16,16))
        
        # Winrate Donut Chart
        self._donut = DonutChart(top, size=80)
        self._donut.pack(side="left", padx=10)
        self._summary_lbl = tk.Label(top, text="FILTERED WR", bg=BG, fg=FG2, font=("Segoe UI", 7, "bold"))
        self._summary_lbl.pack(side="left")

        # ── Split: defense list (top) + offense breakdown (bottom)
        pane = tk.PanedWindow(self, orient="vertical", bg=BORDER,
                              sashwidth=6, sashrelief="flat")
        pane.pack(fill="both", expand=True, padx=20, pady=(0,12))

        # Defense treeview
        def_frame = tk.Frame(pane, bg=BG)
        cols = ("id","Guild","Composition","Wins","Losses","Win Rate","Global WR")
        tf, self.tree = scrolled_tree(def_frame, cols, heights=12)
        tf.pack(fill="both", expand=True)
        for col, w in zip(cols, [40,130,270,55,60,110,110]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w" if col in ("Guild","Composition") else "center")
        self.tree.column("id", width=0, stretch=False)
        self.tree.tag_configure("win",  foreground=WIN_CLR)
        self.tree.tag_configure("warn", foreground=GOLD)
        self.tree.tag_configure("crit", foreground=LOSS_CLR)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        pane.add(def_frame, stretch="always")

        # Offense breakdown panel
        off_frame = tk.Frame(pane, bg=BG)
        hdr2 = tk.Frame(off_frame, bg=BG); hdr2.pack(fill="x", pady=(6,2))
        self._off_title = tk.Label(hdr2, text="↑ Select a defense to see your offenses vs it",
                                   bg=BG, fg=FG2, font=FONT_SM)
        self._off_title.pack(side="left", padx=4)
        styled_btn(hdr2, "+ Record Battle", self._quick_record, ACCENT, width=14).pack(side="right", padx=4)
        off_cols = ("Name","Composition","Battles","Wins","Losses","Win Rate")
        tf2, self.off_tree = scrolled_tree(off_frame, off_cols, heights=6)
        tf2.pack(fill="both", expand=True)
        for col, w in zip(off_cols, [130,270,70,55,60,110]):
            self.off_tree.heading(col, text=col)
            self.off_tree.column(col, width=w, anchor="w" if col in ("Name","Composition") else "center")
        self.off_tree.tag_configure("win",  foreground=WIN_CLR)
        self.off_tree.tag_configure("warn", foreground=GOLD)
        self.off_tree.tag_configure("crit", foreground=LOSS_CLR)
        pane.add(off_frame, stretch="always")

        self.refresh()

    def refresh(self):
        self._all_rows = list(db.get_defense_stats())
        self._apply_filter()
        # Refresh offense panel if something selected
        sel = self.tree.selection()
        if sel:
            def_id = self.tree.item(sel[0], "values")[0]
            self._load_offense_breakdown(int(def_id))

    def _apply_filter(self):
        query_raw = self._search_var.get().lower().strip()
        query_parts = query_raw.split() # Split by space for fuzzy matching
        tier = self._tier_var.get()
        self.tree.delete(*self.tree.get_children())
        
        filtered_wins = 0
        filtered_total = 0
        
        for r in self._all_rows:
            comp_clean = (r["comp"] or "").lower().replace("/", " ") # Remove slashes for matching
            label_lower = (r["label"] or "").lower()
            r_tier = r["tier"] if "tier" in r.keys() else "5*"

            # Tier filter
            if tier != "All" and r_tier != tier:
                continue

            # Match ALL parts of the query (Fuzzy)
            match = True
            for part in query_parts:
                if part not in comp_clean and part not in label_lower:
                    match = False
                    break
            
            if not match:
                continue
            
            wins_v = r["wins"] or 0; tot = r["total"] or 0
            filtered_wins += wins_v
            filtered_total += tot
            
            wr = winrate_str(wins_v, tot)
            tag = get_wr_tag(wins_v, tot)
            g_wins, g_tot = r["g_wins"] or 0, r["g_total"] or 0
            g_wr = winrate_str(g_wins, g_tot)
            
            self.tree.insert("", "end", tags=(tag,),
                values=(r["id"], r["label"] or "", r["comp"], wins_v, tot - wins_v, wr, g_wr))
        
        # Update Donut Chart
        self._donut.update_stats(filtered_wins, filtered_total)

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if sel:
            def_id = self.tree.item(sel[0], "values")[0]
            self._load_offense_breakdown(int(def_id))

    def _load_offense_breakdown(self, def_id):
        # Update title with defense comp
        row = next((r for r in self._all_rows if r["id"] == def_id), None)
        if row:
            lbl = f"  vs  {row['label'] + ' — ' if row['label'] else ''}{row['comp']}"
            self._off_title.config(text=f"🛡 My Offenses{lbl}", fg=FG)
        self.off_tree.delete(*self.off_tree.get_children())
        for r in db.get_offense_stats_for_defense(def_id):
            wins_v = r["wins"] or 0; tot = r["total"] or 0
            wr = winrate_str(wins_v, tot)
            tag = get_wr_tag(wins_v, tot)
            self.off_tree.insert("", "end", tags=(tag,),
                values=(r["label"], r["comp"], tot, wins_v, tot-wins_v, wr))

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel: messagebox.showinfo("Select", "Please select a defense first."); return None
        return int(sel[0])

    def _quick_record(self):
        def_id = self._selected_id()
        if def_id is None: return
        offenses = db.get_offenses()
        if not offenses:
            messagebox.showwarning("No Offenses", "Add at least one offense in My Offenses first."); return
        dlg = QuickBattleDialog(self, def_id, offenses)
        if dlg.result:
            off_id, result, guild, notes = dlg.result
            db.add_battle(def_id, off_id, result, guild, notes)
            self.refresh(); self.on_change()

    def _add(self):
        dlg = RecordDialog(self, "Add Defense", show_label=True)
        if dlg.result:
            db.add_defense(*dlg.result); self.refresh(); self.on_change()

    def _edit(self):
        def_id = self._selected_id()
        if def_id is None: return
        row = next((r for r in db.get_defenses() if r["id"] == def_id), None)
        if not row: return
        dlg = RecordDialog(self, "Edit Defense", initial=(row["label"],row["monster1"],row["monster2"],row["monster3"],row["notes"],row["tier"]))
        if dlg.result:
            db.update_defense(def_id, *dlg.result); self.refresh(); self.on_change()

    def _delete(self):
        def_id = self._selected_id()
        if def_id is None: return
        if messagebox.askyesno("Delete", "Delete this defense and all its battle records?"):
            db.delete_defense(def_id); self.refresh(); self.on_change()

    def _clear_all(self):
        if messagebox.askyesno("Clear All Defenses", "Are you sure you want to clear ALL defenses?\nThis will also wipe all associated battle history!"):
            if messagebox.askyesno("Final Confirmation", "THIS CANNOT BE UNDONE.\nAre you absolutely sure you want to delete everything?"):
                db.clear_defenses()
                self.refresh(); self.on_change()


# ── Offenses Tab ──────────────────────────────────────────
class OffensesTab(tk.Frame):
    def __init__(self, parent, on_change):
        super().__init__(parent, bg=BG)
        self.on_change = on_change
        tk.Label(self, text="🛡  My Offenses", bg=BG, fg=FG, font=FONT_H).pack(anchor="w", padx=20, pady=(16,4))
        tk.Label(self, text="Your private offense team compositions.", bg=BG, fg=FG2, font=FONT_SM).pack(anchor="w", padx=20)
        bf = tk.Frame(self, bg=BG); bf.pack(anchor="w", padx=20, pady=10)
        styled_btn(bf, "+ Add Offense", self._add, ACCENT2).pack(side="left", padx=(0,8))
        styled_btn(bf, "✏ Edit", self._edit, CARD).pack(side="left", padx=(0,8))
        styled_btn(bf, "🗑 Delete", self._delete, "#6b2f2f").pack(side="left", padx=(0,8))
        styled_btn(bf, "🗑 Clear All", self._clear_all, "#4a1c1c", width=12).pack(side="left")
        cols = ("id","Name","Composition","Wins","Losses","Win Rate","Notes")
        tf, self.tree = scrolled_tree(self, cols, heights=20)
        tf.pack(fill="both", expand=True, padx=20, pady=(0,16))
        for col, w in zip(cols, [40,120,260,50,55,100,200]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center" if col not in ("Composition","Name","Notes") else "w")
        self.tree.column("id", width=0, stretch=False)
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for r in db.get_offense_stats():
            wr = winrate_str(r["wins"] or 0, r["total"] or 0)
            self.tree.insert("", "end", iid=str(r["id"]),
                values=(r["id"], r["name"], r["comp"],
                        r["wins"] or 0, r["losses"] or 0, wr, ""))

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel: messagebox.showinfo("Select", "Please select an offense first."); return None
        return int(sel[0])

    def _add(self):
        dlg = RecordDialog(self, "Add Offense", show_label=True, label_text="Team Name")
        if dlg.result:
            db.add_offense(*dlg.result); self.refresh(); self.on_change()

    def _edit(self):
        off_id = self._selected_id()
        if off_id is None: return
        row = next((r for r in db.get_offenses() if r["id"] == off_id), None)
        if not row: return
        dlg = RecordDialog(self, "Edit Offense", show_label=True, label_text="Team Name", initial=(row["label"],row["monster1"],row["monster2"],row["monster3"],row["notes"]))
        if dlg.result:
            db.update_offense(off_id, *dlg.result); self.refresh(); self.on_change()

    def _delete(self):
        off_id = self._selected_id()
        if off_id is None: return
        if messagebox.askyesno("Delete", "Delete this offense and all its battle records?"):
            db.delete_offense(off_id); self.refresh(); self.on_change()

    def _clear_all(self):
        if messagebox.askyesno("Clear All Offenses", "Are you sure you want to clear ALL offenses?\nThis will also wipe all associated battle history!"):
            if messagebox.askyesno("Final Confirmation", "THIS CANNOT BE UNDONE.\nAre you absolutely sure you want to delete everything?"):
                db.clear_offenses()
                self.refresh(); self.on_change()

# ── Battle Log Tab ────────────────────────────────────────
class BattleLogTab(tk.Frame):
    def __init__(self, parent, on_change):
        super().__init__(parent, bg=BG)
        self.on_change = on_change
        tk.Label(self, text="📋  Battle Log", bg=BG, fg=FG, font=FONT_H).pack(anchor="w", padx=20, pady=(16,4))
        tk.Label(self, text="Record the result of each siege battle.", bg=BG, fg=FG2, font=FONT_SM).pack(anchor="w", padx=20)

        # ── Record form
        form = lf(self, "Record New Battle")
        form.pack(fill="x", padx=20, pady=12)
        row1 = tk.Frame(form, bg=PANEL); row1.pack(fill="x", padx=12, pady=8)
        tk.Label(row1, text="Defense", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=0, column=0, sticky="w")
        self.def_search = SearchEntry(row1, width=32)
        self.def_search.grid(row=1, column=0, padx=(0,16))
        
        tk.Label(row1, text="My Offense", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=0, column=1, sticky="w")
        self.off_search = SearchEntry(row1, width=32)
        self.off_search.grid(row=1, column=1, padx=(0,16))

        tk.Label(row1, text="Guild", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=0, column=2, sticky="w")
        self.guild_e = entry(row1, 16)
        self.guild_e.grid(row=1, column=2, padx=(0,16))

        tk.Label(row1, text="Result", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=0, column=3, sticky="w")
        self.result_var = tk.StringVar(value="Win")
        rf = tk.Frame(row1, bg=PANEL); rf.grid(row=1, column=3, padx=(0,16))
        for v in ("Win","Loss"):
            rb = tk.Radiobutton(rf, text=v, variable=self.result_var, value=v,
                                bg=PANEL, fg=WIN_CLR if v=="Win" else LOSS_CLR,
                                selectcolor=CARD, font=FONT_B, activebackground=PANEL)
            rb.pack(side="left", padx=4)
        tk.Label(row1, text="Notes", bg=PANEL, fg=FG2, font=FONT_SM).grid(row=0, column=4, sticky="w")
        self.note_e = entry(row1, 15); self.note_e.grid(row=1, column=4, padx=(0,16))
        styled_btn(row1, "Record ✓", self._record, ACCENT).grid(row=1, column=5, padx=4)
        styled_btn(row1, "🗑 Delete", self._delete, LOSS_CLR, width=10).grid(row=1, column=6, padx=4)
        styled_btn(row1, "🗑 Clear Log", self._clear_all, "#4a1c1c", width=12).grid(row=1, column=7, padx=(0,4))

        # ── Log tree
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(4,0))
        cols = ("id","Date","Defense","Offense","Result","Notes")
        tf, self.tree = scrolled_tree(self, cols, heights=18)
        tf.pack(fill="both", expand=True, padx=20, pady=(4,12))
        widths = [40,145,255,210,65,200]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center" if col == "Result" else "w")
        self.tree.column("id", width=0, stretch=False)
        self.tree.tag_configure("win",  foreground=WIN_CLR)
        self.tree.tag_configure("loss", foreground=LOSS_CLR)
        # Right-click context menu
        self._ctx = tk.Menu(self.tree, tearoff=0, bg=CARD2, fg=FG,
                            activebackground=ACCENT, activeforeground=FG,
                            font=FONT, bd=0, relief="flat")
        self._ctx.add_command(label="🗑  Delete this entry", command=self._delete)
        self.tree.bind("<Button-3>", self._show_ctx)
        self.refresh()

    def _show_ctx(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self._ctx.tk_popup(event.x_root, event.y_root)



    def refresh(self):
        # Rebuild comboboxes (Clean display without IDs)
        defs = db.get_defenses()
        offs = db.get_offenses()
        self._def_map = {}
        for r in defs:
            comp = r['monster1']
            if r['monster2']: comp += ' / ' + r['monster2']
            if r['monster3']: comp += ' / ' + r['monster3']
            label = r['label'] or "Unknown"
            display = f"{label} — {comp}"
            # Collision handling
            if display in self._def_map:
                display = f"{label} ({r['id']}) — {comp}"
            self._def_map[display] = r['id']

        self._off_map = {}
        for r in offs:
            comp = r['monster1']
            if r['monster2']: comp += ' / ' + r['monster2']
            if r['monster3']: comp += ' / ' + r['monster3']
            name = r['label'] or comp
            display = f"{name} — {comp}"
            if display in self._off_map:
                display = f"{name} ({r['id']}) — {comp}"
            self._off_map[display] = r['id']
        
        self.def_search.set_all_values(list(self._def_map.keys()))
        self.off_search.set_all_values(list(self._off_map.keys()))

        if not self.def_search.get() and self._def_map:
            self.def_search.set(list(self._def_map.keys())[0])
        if not self.off_search.get() and self._off_map:
            self.off_search.set(list(self._off_map.keys())[0])

        self.tree.delete(*self.tree.get_children())
        for r in db.get_battles():
            def_lbl = (r["def_label"] + " — " if r["def_label"] else "") + r["defense_str"]
            tag = "win" if r["result"]=="Win" else "loss"
            self.tree.insert("", "end", iid=str(r["id"]), tags=(tag,),
                values=(r["id"], r["battle_date"], def_lbl, r["off_label"]+(" — "+r["offense_str"] if r["offense_str"] else ""),
                        r["result"], r["notes"] or ""))

    def _record(self):
        dk, ok = self.def_search.get(), self.off_search.get()
        if dk not in self._def_map or ok not in self._off_map:
            messagebox.showwarning("Missing", "Select a valid defense and offense from the lists."); return
        db.add_battle(self._def_map[dk], self._off_map[ok],
                      self.result_var.get(), self.guild_e.get().strip(), self.note_e.get().strip())
        self.note_e.delete(0,"end")
        self.guild_e.delete(0, "end")
        self.refresh(); self.on_change()

    def _delete(self):
        sel = self.tree.selection()
        if not sel: messagebox.showinfo("Select", "Select a battle entry to delete."); return
        if messagebox.askyesno("Delete", "Remove this battle record?"):
            db.delete_battle(int(sel[0])); self.refresh(); self.on_change()

    def _clear_all(self):
        if messagebox.askyesno("Clear Battle Log", "Are you sure you want to clear ALL battle records?\nThis will keep your defenses and offenses intact."):
            if messagebox.askyesno("Final Confirmation", "THIS CANNOT BE UNDONE.\nAre you absolutely sure you want to delete everything?"):
                db.clear_battles()
                self.refresh(); self.on_change()

# ── Dashboard Tab ─────────────────────────────────────────
class DashboardTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        # ── Header
        hdr = tk.Frame(self, bg=BG); hdr.pack(fill="x", padx=20, pady=(18,4))
        tk.Label(hdr, text="📊  Siege Dashboard", bg=BG, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        
        # Toggles in header
        t_f = tk.Frame(hdr, bg=BG)
        t_f.pack(side="right")
        
        self._scout_var = tk.BooleanVar(value=db.get_setting("auto_discovery", "True") == "True")
        cb_scout = tk.Checkbutton(t_f, text="Live Scouting", variable=self._scout_var,
                            bg=BG, fg=FG2, activebackground=BG, activeforeground=FG,
                            selectcolor=SIDE, font=("Segoe UI", 9, "bold"),
                            cursor="hand2", command=self._toggle_scouting)
        cb_scout.pack(side="left", padx=10)

        self._guild_var = tk.BooleanVar(value=db.get_setting("import_all_guild", "False") == "True")
        cb_guild = tk.Checkbutton(t_f, text="Import Entire Guild", variable=self._guild_var,
                            bg=BG, fg=FG2, activebackground=BG, activeforeground=FG,
                            selectcolor=SIDE, font=("Segoe UI", 9, "bold"),
                            cursor="hand2", command=self._toggle_guild_import)
        cb_guild.pack(side="left", padx=10)

        tk.Label(self, text="Overview of your siege performance.",
                 bg=BG, fg=FG2, font=FONT_SM).pack(anchor="w", padx=20)

        # ── Stat Cards Row
        self.stat_frame = tk.Frame(self, bg=BG)
        self.stat_frame.pack(fill="x", padx=20, pady=(14, 16))

        # ── Tables Area (Side by Side Grid)
        self.tables_frame = tk.Frame(self, bg=BG)
        self.tables_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.tables_frame.columnconfigure(0, weight=1)
        self.tables_frame.columnconfigure(1, weight=1)
        self.tables_frame.rowconfigure(0, weight=1)

        # ── Hardest Defenses (Left Column)
        left_col = tk.Frame(self.tables_frame, bg=BG)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._section_lbl(left_col, " 🔴  Hardest Defenses ")
        
        lf_d = tk.Frame(left_col, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        lf_d.pack(fill="both", expand=True, pady=(0,12))
        cols = ("Composition","Last Faced","Battles","Wins","Losses","Win Rate")
        tf, self.def_tree = scrolled_tree(lf_d, cols, heights=7)
        tf.pack(fill="both", expand=True)
        for col, w in zip(cols, [220,110,60,50,55,100]):
            self.def_tree.heading(col, text=col)
            self.def_tree.column(col, width=w, anchor="w" if col in ("Composition","Last Faced") else "center")

        # ── Best Offenses (Right Column)
        right_col = tk.Frame(self.tables_frame, bg=BG)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self._section_lbl(right_col, " 🟢  Best Offenses ")
        
        lf_o = tk.Frame(right_col, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        lf_o.pack(fill="both", expand=True, pady=(0,16))
        cols2 = ("Name","Composition","Battles","Wins","Losses","Win Rate")
        tf2, self.off_tree = scrolled_tree(lf_o, cols2, heights=7)
        tf2.pack(fill="both", expand=True)
        for col, w in zip(cols2, [110,220,60,50,55,100]):
            self.off_tree.heading(col, text=col)
            self.off_tree.column(col, width=w, anchor="w" if col in ("Name","Composition") else "center")

        self.refresh()
        self.status_lbl = tk.Label(self, text="System Ready", bg=BG, fg=FG3, font=("Segoe UI", 8))
        self.status_lbl.pack(side="bottom", anchor="e", padx=20, pady=4)

    def _section_lbl(self, parent, text):
        row = tk.Frame(parent, bg=BG); row.pack(fill="x", pady=(0,6))
        pill = tk.Frame(row, bg=CARD2, padx=10, pady=3)
        pill.pack(side="left")
        tk.Label(pill, text=text, bg=CARD2, fg=FG2, font=("Segoe UI", 9, "bold")).pack()
        tk.Frame(row, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(8,0), pady=6)

    def set_status(self, text):
        self.status_lbl.config(text=text)

    def _toggle_scouting(self):
        db.set_setting("auto_discovery", str(self._scout_var.get()))

    def _toggle_guild_import(self):
        db.set_setting("import_all_guild", str(self._guild_var.get()))

    def _section(self, text):
        row = tk.Frame(self, bg=BG); row.pack(fill="x", padx=20, pady=(0,6))
        pill = tk.Frame(row, bg=CARD2, padx=10, pady=3)
        pill.pack(side="left")
        tk.Label(pill, text=text, bg=CARD2, fg=FG2, font=("Segoe UI", 9, "bold")).pack()
        tk.Frame(row, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(8,0), pady=6)

    def _stat_card(self, parent, title, value, color=ACCENT, sub=None):
        # The 'color' is now the persistent border color
        outer = tk.Frame(parent, bg=color, padx=2, pady=2)
        inner = tk.Frame(outer, bg=CARD, padx=20, pady=16)
        inner.pack(fill="both", expand=True)
        
        l1 = tk.Label(inner, text=title.upper(), bg=CARD, fg=FG2, font=("Segoe UI", 8, "bold"))
        l1.pack(anchor="w")
        l2 = tk.Label(inner, text=value, bg=CARD, fg=color, font=("Segoe UI", 26, "bold"))
        l2.pack(anchor="w", pady=(4,0))
        l3 = None
        if sub:
            l3 = tk.Label(inner, text=sub, bg=CARD, fg=FG2, font=("Segoe UI", 8))
            l3.pack(anchor="w")
            
        glow_color = _HOVER.get(color, _lighten(color))

        def on_enter(e): 
            outer.config(bg=glow_color)
            inner.config(bg=CARD2)
            l1.config(bg=CARD2); l2.config(bg=CARD2)
            if l3: l3.config(bg=CARD2)
            
        def on_leave(e): 
            outer.config(bg=color)
            inner.config(bg=CARD)
            l1.config(bg=CARD); l2.config(bg=CARD)
            if l3: l3.config(bg=CARD)

        inner.bind("<Enter>", on_enter)
        inner.bind("<Leave>", on_leave)
        for w in (l1, l2, l3) if l3 else (l1, l2):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            
        return outer

    def _fade_color(self, widget, start_hex, end_hex, steps=40, current_step=0):
        if not widget.winfo_exists(): return
        def hex_to_rgb(h): return tuple(int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        def rgb_to_hex(rgb): return '#%02x%02x%02x' % rgb
        s_rgb, e_rgb = hex_to_rgb(start_hex), hex_to_rgb(end_hex)
        new_rgb = tuple(int(s_rgb[i] + (e_rgb[i] - s_rgb[i]) * (current_step / steps)) for i in range(3))
        widget.config(bg=rgb_to_hex(new_rgb))
        if current_step < steps:
            aid = self.after(25, lambda: self._fade_color(widget, start_hex, end_hex, steps, current_step + 1))
            self._after_ids.append(aid)

    def refresh(self):
        # Cancel any pending refresh tasks to prevent double cards
        if hasattr(self, "_after_ids"):
            for aid in self._after_ids:
                try: self.after_cancel(aid)
                except: pass
        self._after_ids = []

        # Clean up existing cards
        for w in self.stat_frame.winfo_children(): w.destroy()
        
        battles = db.get_battles()
        total, wins = len(battles), sum(1 for b in battles if b["result"]=="Win")
        losses = total - wins
        wr_pct = int(wins/total*100) if total else 0
        wr = f"{wr_pct}%" if total else "—"

        cards_data = [
            ("Total Battles", str(total), ACCENT2, "all time"),
            ("Wins",          str(wins),  WIN_CLR,  f"{wr_pct}% win rate"),
            ("Losses",        str(losses),LOSS_CLR, f"{100-wr_pct}% loss rate" if total else ""),
            ("Overall Winrate", wr,       ACCENT,   f"{wins}W / {losses}L"),
        ]
        # Simultaneous Fade-in for all cards
        for title, val, clr, sub in cards_data:
            c = self._stat_card(self.stat_frame, title, val, clr, sub)
            c.pack(side="left", padx=(0,12), fill="both", expand=True)
            self._fade_color(c, BG, clr, steps=20)

        # Defenses table — sorted by winrate asc (hardest)
        self.def_tree.delete(*self.def_tree.get_children())
        ds = sorted([r for r in db.get_defense_stats() if r["total"] > 0],
                    key=lambda r: (r["wins"] or 0)/(r["total"] or 1))
        for i, r in enumerate(ds[:10]):
            wins_v = r["wins"] or 0; tot = r["total"] or 0
            wr = winrate_str(wins_v, tot)
            tag = get_wr_tag(wins_v, tot)
            last_date = (r["last_seen"] or "").split()[0]
            tags = (tag, "alt") if i % 2 else (tag,)
            self.def_tree.insert("", "end", tags=tags,
                values=(r["comp"], last_date, tot, wins_v, tot-wins_v, wr))
        self.def_tree.tag_configure("win",  foreground=WIN_CLR)
        self.def_tree.tag_configure("warn", foreground=GOLD)
        self.def_tree.tag_configure("crit", foreground=LOSS_CLR)

        # Offenses table — sorted by winrate desc
        self.off_tree.delete(*self.off_tree.get_children())
        os_ = sorted(db.get_offense_stats(),
                     key=lambda r: (r["wins"] or 0)/(r["total"] or 1), reverse=True)
        for i, r in enumerate(os_[:10]):
            wins_v = r["wins"] or 0; tot = r["total"] or 0
            wr = winrate_str(wins_v, tot)
            tag = get_wr_tag(wins_v, tot)
            tags = (tag, "alt") if i % 2 else (tag,)
            self.off_tree.insert("", "end", tags=tags,
                values=(r["name"], r["comp"], tot, wins_v, tot-wins_v, wr))
        self.off_tree.tag_configure("win",  foreground=WIN_CLR)
        self.off_tree.tag_configure("warn", foreground=GOLD)
        self.off_tree.tag_configure("crit", foreground=LOSS_CLR)

def _parse_node(line: str) -> str:
    """
    Parse a defense node from any flexible format into 'Mon1 / Mon2 / Mon3'.
    Accepts: slashes, commas, or plain spaces as separators.
    Examples:
      'lushen galleon perna'        -> 'Lushen / Galleon / Perna'
      'lushen / galleon / perna'    -> 'Lushen / Galleon / Perna'
      'lushen, galleon, perna'      -> 'Lushen / Galleon / Perna'
      'Water Homunculus Chloe Vero' -> 'Water Homunculus / Chloe / Vero'  (best effort)
    """
    line = line.strip()
    # Already has slashes — just normalize capitalization
    if "/" in line:
        parts = [p.strip().title() for p in line.split("/") if p.strip()]
        return " / ".join(parts)
    # Comma separated
    if "," in line:
        parts = [p.strip().title() for p in line.split(",") if p.strip()]
        return " / ".join(parts)
    # Space separated: split into words and group into up to 3 monsters
    # Heuristic: if exactly 3 words → one word each; else treat as written
    words = line.split()
    if len(words) == 3:
        return " / ".join(w.title() for w in words)
    # For multi-word monsters (e.g. "Water Homunculus"), just title-case the whole line
    return line.title()

# ── Siege Planner Dialog ──────────────────────────────────
class SiegePlannerDialog(tk.Toplevel):
    """Enter enemy defense nodes → AI assigns your offense teams optimally."""
    def __init__(self, parent, model, set_response_cb, ask_btn):
        super().__init__(parent)
        self.title("🗃  Siege Battle Planner")
        self.configure(bg=PANEL)
        self.resizable(True, True)
        self.geometry("640x520")
        self._model = model
        self._set_response = set_response_cb
        self._ask_btn = ask_btn

        tk.Label(self, text="Siege Battle Planner", bg=PANEL, fg=FG, font=FONT_H).pack(padx=20, pady=(14,2))
        tk.Label(self, text="Enter the enemy defense nodes (one per line: Mon1 / Mon2 / Mon3).\nAI will assign your offense teams to maximize wins.",
                 bg=PANEL, fg=FG2, font=FONT_SM, justify="left").pack(padx=20, anchor="w")

        # Defense nodes input
        lf1 = lf(self, " Enemy Defense Nodes ")
        lf1.pack(fill="x", padx=20, pady=(10,4))
        tk.Label(lf1, text="One defense per line. Any format works:", bg=PANEL, fg=FG2, font=FONT_SM).pack(anchor="w", padx=8, pady=(4,0))
        tk.Label(lf1, text="  lushen galleon perna     OR     Lushen / Galleon / Perna     OR     lushen, galleon, perna",
                 bg=PANEL, fg=FG3, font=("Consolas", 9)).pack(anchor="w", padx=8)
        self._def_text = tk.Text(lf1, height=6, bg=CARD2, fg=FG, font=FONT,
                                  insertbackground=FG, relief="flat", bd=4)
        self._def_text.pack(fill="x", padx=8, pady=(2,8))

        # Pre-fill from DB defenses (optional)
        lf2 = lf(self, " Options ")
        lf2.pack(fill="x", padx=20, pady=(0,4))
        opt_row = tk.Frame(lf2, bg=PANEL); opt_row.pack(fill="x", padx=8, pady=6)
        tk.Label(opt_row, text="Notes:", bg=PANEL, fg=FG2, font=FONT_SM).pack(side="left")
        self._notes_e = entry(opt_row, 35); self._notes_e.pack(side="left", padx=(6,16))
        styled_btn(opt_row, "Load My Teams →", self._preview_teams, CARD, width=14).pack(side="left")

        # Teams preview
        self._teams_label = tk.Label(self, text="", bg=PANEL, fg=FG2, font=FONT_SM,
                                     justify="left", wraplength=580)
        self._teams_label.pack(padx=20, anchor="w")
        self._preview_teams()

        # Buttons
        bf = tk.Frame(self, bg=PANEL); bf.pack(side="bottom", fill="x", padx=20, pady=12)
        styled_btn(bf, "Cancel", self.destroy, CARD, width=10).pack(side="right", padx=4)
        styled_btn(bf, "✨ Generate Plan", self._generate, ACCENT, width=16).pack(side="right", padx=4)

        self.grab_set()

    def _preview_teams(self):
        teams = ai_advisor.build_offense_teams_for_planner()
        if not teams:
            self._teams_label.config(text="No offense teams in database yet.")
            return
        lines = [f"  {t['label']} ({t['comp']}) — {t['history_text']}" for t in teams]
        self._teams_label.config(
            text=f"Your {len(teams)} offense team(s):\n" + "\n".join(lines)
        )

    def _generate(self):
        raw = self._def_text.get("1.0", "end").strip()
        if not raw:
            messagebox.showwarning("Missing", "Enter at least one enemy defense node.", parent=self)
            return
        nodes = [_parse_node(line) for line in raw.splitlines() if line.strip()]
        teams = ai_advisor.build_offense_teams_for_planner()
        if not teams:
            messagebox.showwarning("No Teams", "Add offense teams in My Offenses first.", parent=self)
            return
        notes = self._notes_e.get().strip()
        model = self._model

        self._set_response(f"⏳ Planning {len(nodes)} node(s) with {len(teams)} team(s)…", is_status=True)
        self._ask_btn.config(state="disabled")
        self.destroy()

        def run():
            resp = ai_advisor.plan_siege(model, nodes, teams, notes)
            import tkinter as _tk
            self._ask_btn.master.after(0, lambda: self._set_response(resp))
            self._ask_btn.master.after(0, lambda: self._ask_btn.config(state="normal"))

        import threading as _t
        _t.Thread(target=run, daemon=True).start()

# ── AI Advisor Tab (Coming Soon) ─────────────────────────
class AIAdvisorTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        # Centered "Coming Soon" card
        outer = tk.Frame(self, bg=BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")
        card = tk.Frame(outer, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(padx=40, pady=40)
        tk.Label(card, text="🤖", bg=CARD, fg=FG, font=("Segoe UI", 48)).pack(pady=(32,8))
        tk.Label(card, text="AI Counter Advisor", bg=CARD, fg=FG,
                 font=("Segoe UI", 18, "bold")).pack()
        tk.Label(card, text="Coming Soon", bg=CARD, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).pack(pady=(4,0))
        tk.Label(card, text="Powered by local AI to suggest counter teams\nbased on your personal win/loss history.",
                 bg=CARD, fg=FG2, font=FONT_SM, justify="center").pack(pady=(8,32))

    def refresh(self):
        pass  # Nothing to refresh


# ── License Activation Window ────────────────────────
class LicenseWindow(tk.Tk):
    """Standalone activation screen shown before the main app."""
    def __init__(self):
        super().__init__()
        self.title("Siege Database — Activation")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("480x420")
        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 480) // 2
        y = (self.winfo_screenheight() - 420) // 2
        self.geometry(f"480x420+{x}+{y}")
        self.activated = False
        self._build()

    def _build(self):
        # Gradient-feel top accent bar
        tk.Frame(self, bg=ACCENT, height=4).pack(fill="x")

        # Logo section
        logo_f = tk.Frame(self, bg=BG)
        logo_f.pack(pady=(36, 0))
        tk.Label(logo_f, text="⚡", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 42)).pack()
        tk.Label(logo_f, text="SIEGE DATABASE", bg=BG, fg=FG,
                 font=("Segoe UI", 20, "bold")).pack(pady=(4,0))
        tk.Label(logo_f, text="Summoners War  ·  Beta Access", bg=BG, fg=FG2,
                 font=("Segoe UI", 10)).pack(pady=(2,0))

        # Divider
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=48, pady=28)

        # Key entry area
        entry_f = tk.Frame(self, bg=BG)
        entry_f.pack(padx=48, fill="x")
        tk.Label(entry_f, text="License Key", bg=BG, fg=FG2,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0,6))

        # Styled entry with border frame trick
        border_f = tk.Frame(entry_f, bg=BORDER, padx=1, pady=1)
        border_f.pack(fill="x")
        inner_f = tk.Frame(border_f, bg=CARD)
        inner_f.pack(fill="x")
        self._key_var = tk.StringVar()
        self._key_var.trace_add("write", self._on_key_change)
        self._key_entry = tk.Entry(
            inner_f, textvariable=self._key_var,
            bg=CARD, fg=FG, font=("Consolas", 13, "bold"),
            relief="flat", bd=10, insertbackground=ACCENT,
            justify="center"
        )
        self._key_entry.pack(fill="x")
        self._key_entry.focus()

        # Format hint
        self._hint = tk.Label(entry_f, text="Format:  SDBT-XXXX-XXXX-XXXX-XXXX",
                              bg=BG, fg=FG3, font=("Segoe UI", 8))
        self._hint.pack(pady=(6,0))

        # Status message
        self._status = tk.Label(self, text="", bg=BG, fg=LOSS_CLR, font=("Segoe UI", 9))
        self._status.pack(pady=(12,0))

        # Activate button
        self._btn = styled_btn(self, "  Activate  ", self._activate, ACCENT, width=18)
        self._btn.pack(pady=(16,0))

        # Bind Enter key
        self.bind("<Return>", lambda e: self._activate())

        # Auto-format key as user types (insert dashes)
        self._prev_len = 0

    def _on_key_change(self, *_):
        """Auto-insert dashes and uppercase as the user types."""
        raw = self._key_var.get().upper().replace("-", "").replace(" ", "")
        # Limit to 20 alphanum chars (5 groups of 4)
        raw = raw[:20]
        # Re-insert dashes every 4 chars
        parts = [raw[i:i+4] for i in range(0, len(raw), 4)]
        formatted = "-".join(parts)
        # Only update if different to avoid cursor jump
        if formatted != self._key_var.get():
            self._key_var.set(formatted)
            self._key_entry.icursor("end")
        self._status.config(text="")

    def _activate(self):
        key = self._key_var.get().strip()
        if not key:
            self._status.config(text="⚠  Please enter your license key.", fg=GOLD)
            return
        if lic.validate_key(key):
            lic.save_key(key)
            self._status.config(text="✓  Activation successful!", fg=WIN_CLR)
            self._btn.config(state="disabled")
            self.after(800, self._launch)
        else:
            self._status.config(text="✗  Invalid key. Please check and try again.", fg=LOSS_CLR)
            self._key_entry.config(bg="#1a0a0a")
            self.after(600, lambda: self._key_entry.config(bg=CARD))

    def _launch(self):
        self.activated = True
        self.destroy()


# ── Main App ──────────────────────────────────────────────
class SiegeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        db.init_db()
        self.title("Siege Database v2  —  Summoners War")
        self.geometry("1300x800")
        self.minsize(1000, 600)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.current_tab = None
        self._build_ui()
        # Start live ingest server
        self._server_ok = ingest_server.start(
            refresh_cb=lambda: self.after(0, self._on_change),
            notify_cb=lambda: self.after(0, self._on_live_ingest),
            discovery_cb=lambda c: self.after(0, lambda: self._on_discovery_ingest(c)),
            wizard_getter=lambda: self._wizard_name_var.get().strip()
        )
        self.after(100, self._update_live_status)
        # First-run: prompt for IGN if not set
        self.after(300, self._check_ign)

    def _on_closing(self):
        db.backup_db()
        ingest_server.stop()
        self.destroy()

    def _update_live_status(self):
        """Set the live status dot based on whether the ingest server is active and receiving pings."""
        if not self._server_ok:
            self._live_status.config(text="🔴  Offline", fg=LOSS_CLR)
            return

        # Check if we've had contact in the last 25 seconds (pings are every 10s)
        import time
        last = ingest_server.get_last_contact()
        is_live = (time.time() - last) < 25

        if is_live:
            self._live_status.config(text="🟢  Live", fg=WIN_CLR)
        else:
            self._live_status.config(text="🟡  Idle", fg=GOLD)
            
        # Re-check every 5 seconds
        self.after(5000, self._update_live_status)

    def _on_live_ingest(self, result):
        """Called on main thread when the SWEX plugin sends a battle."""
        self._on_change()
        if result.get("status") == "ok":
            msg = f"⚡ Imported: {result.get('offense')} vs {result.get('defense')}"
            self.dashboard.set_status(msg)
            self._live_status.config(text="⚡ Battle imported!", fg=WIN_CLR)
        elif result.get("status") == "skipped":
            msg = f"⚠ Skipped: {result.get('reason')}"
            self.dashboard.set_status(msg)
            self._live_status.config(text="⚠ Battle skipped", fg=GOLD)
        elif result.get("status") == "duplicate":
            self.dashboard.set_status("ℹ Skipped: Duplicate battle")
            self._live_status.config(text="ℹ Duplicate skip", fg=FG2)

        self.after(3000, self._update_live_status)

    def _on_discovery_ingest(self, result):
        """Called on main thread when the SWEX plugin sends a discovery packet."""
        self._on_change()
        count = result.get("count", 0)
        if result.get("status") == "ok":
            if count > 0:
                msg = f"🔭 {count} Defenses discovered!"
                self.dashboard.set_status(msg)
                self._live_status.config(text=msg, fg=WIN_CLR)
            else:
                self.dashboard.set_status("🔭 No new defenses found.")
                self._live_status.config(text="🔭 No new defenses found.", fg=GOLD)
        elif result.get("status") == "disabled":
            self.dashboard.set_status("ℹ Scouting is disabled (see toggle)")
        
        self.after(3000, self._update_live_status)

    def _check_ign(self):
        """Prompt for IGN on first run if the field is empty."""
        if not self._wizard_name_var.get().strip():
            ign = simpledialog.askstring(
                "Welcome to Siege Database!",
                "Enter your Summoners War in-game name (IGN).\n"
                "This is used to identify your battles when importing siege logs.",
                parent=self
            )
            if ign:
                self._wizard_name_var.set(ign.strip())

    def _build_ui(self):
        # ── Header bar
        hdr = tk.Frame(self, bg=PANEL)
        hdr.pack(fill="x")
        # Logo area
        logo = tk.Frame(hdr, bg=PANEL); logo.pack(side="left", padx=20, pady=10)
        tk.Label(logo, text="⚡  SIEGE DATABASE", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(logo, text="  · Summoners War", bg=PANEL, fg=FG2, font=FONT).pack(side="left")
        # Right side
        right = tk.Frame(hdr, bg=PANEL); right.pack(side="right", padx=12, pady=8)
        self._import_status = tk.Label(right, text="", bg=PANEL, fg=FG2, font=FONT_SM)
        self._import_status.pack(side="right", padx=(8,0))
        styled_btn(right, "⬇ Import Siege Logs", self._import_siege_logs, GOLD, width=16).pack(side="right", padx=(0,6))
        styled_btn(right, "⬇ Import SWEX", self._import_swex, ACCENT2, width=14).pack(side="right")
        # Live status indicator
        self._live_status = tk.Label(right, text="", bg=PANEL, fg=FG2,
                                     font=("Segoe UI", 9, "bold"))
        self._live_status.pack(side="right", padx=(0, 14))
        # Wizard name setting — group in sub-frame to keep label left of entry
        ign_frame = tk.Frame(right, bg=PANEL)
        ign_frame.pack(side="right", padx=(16, 8))
        tk.Label(ign_frame, text="My IGN:", bg=PANEL, fg=FG2, font=FONT_SM).pack(side="left", padx=(0,4))
        self._wizard_name_var = tk.StringVar(value="")
        wiz_e = tk.Entry(ign_frame, textvariable=self._wizard_name_var, width=12,
                         bg=CARD, fg=FG, font=FONT, insertbackground=FG,
                         relief="flat", bd=3)
        wiz_e.pack(side="left")

        # Separator
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── Navigation tab bar (styled)
        self.btn_bar = tk.Frame(self, bg=SIDE)
        self.btn_bar.pack(fill="x")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── Content
        nb_frame = tk.Frame(self, bg=BG)
        nb_frame.pack(fill="both", expand=True)

        self.pages = {}
        self.tab_btns = {}

        self.dashboard  = DashboardTab(nb_frame)
        self.defenses   = DefensesTab(nb_frame, self._on_change)
        self.offenses   = OffensesTab(nb_frame, self._on_change)
        self.battlelog  = BattleLogTab(nb_frame, self._on_change)
        self.ai_tab     = AIAdvisorTab(nb_frame)

        NAV = [("📊  Dashboard", "Dashboard"), ("⚔  Defenses", "Defenses"),
               ("🛡  My Offenses", "My Offenses"), ("📋  Battle Log", "Battle Log"),
               ("🤖  Coming Soon", "AI Advisor")]
        for label_txt, name in NAV:
            page = {"Dashboard": self.dashboard, "Defenses": self.defenses,
                    "My Offenses": self.offenses, "Battle Log": self.battlelog,
                    "AI Advisor": self.ai_tab}[name]
            self.pages[name] = page
            b = tk.Button(self.btn_bar, text=label_txt, font=FONT_B, relief="flat", bd=0,
                          padx=20, pady=10, cursor="hand2", bg=SIDE, fg=FG2,
                          activebackground=PANEL, activeforeground=FG,
                          command=lambda n=name: self._show(n))
            b.pack(side="left")
            self.tab_btns[name] = b
            
            # Hover animations
            b.bind("<Enter>", lambda e, btn=b: btn.config(bg=PANEL, fg=FG))
            b.bind("<Leave>", lambda e, btn=b, n=name: self._reset_tab_style(n))

        self._show("Dashboard")

    def _reset_tab_style(self, name):
        """Helper for hover animations — ensures active tab stays lit."""
        if name == self.current_tab:
            self.tab_btns[name].config(bg=ACCENT_BG, fg=ACCENT)
        else:
            self.tab_btns[name].config(bg=SIDE, fg=FG2)

    def _show(self, name):
        for n, p in self.pages.items():
            p.pack_forget()
            self.tab_btns[n].config(bg=SIDE, fg=FG2)
        self.pages[name].pack(fill="both", expand=True)
        # Active tab: brighter bg + accent underline effect via fg color
        self.tab_btns[name].config(bg=PANEL, fg=ACCENT)
        self.current_tab = name
        if name == "Dashboard":
            self.dashboard.refresh()

    def _import_swex(self):
        path = filedialog.askopenfilename(
            title="Select your SWEX JSON file",
            initialdir=r"C:\Users\Evan\Desktop\Summoners War Exporter Files",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        self._import_status.config(text="Importing SWEX…", fg=ACCENT2)
        self.update_idletasks()

        def run():
            try:
                results = importer.run_import(json_path=path)
                msg_parts = []
                if "offenses_imported" in results:
                    msg_parts.append(f"{results['offenses_imported']} offenses imported, {results['offenses_skipped']} skipped")
                if results.get("battles_imported"):
                    msg_parts.append(f"{results['battles_imported']} old-format battles imported")
                msg = " | ".join(msg_parts) if msg_parts else "Nothing new to import."
                self.after(0, lambda: self._finish_import(msg))
            except Exception as e:
                self.after(0, lambda: self._finish_import(f"Error: {e}", error=True))

        threading.Thread(target=run, daemon=True).start()

    def _import_siege_logs(self):
        wizard = self._wizard_name_var.get().strip()
        if not wizard:
            messagebox.showwarning("IGN Required",
                "Enter your in-game name in the 'My IGN' field first.")
            return
        import os
        default_dir = importer.SWEX_FILES_PATH if os.path.isdir(importer.SWEX_FILES_PATH) \
                      else os.path.expanduser("~")
        folder = filedialog.askdirectory(
            title="Select your SWGT logs folder",
            initialdir=default_dir
        )
        if not folder:
            return
        self._import_status.config(text=f"Scanning for '{wizard}'…", fg=GOLD)
        self.update_idletasks()

        def run():
            try:
                imp, skip = importer.import_battles_from_siege_logs(
                    log_dir=folder, my_wizard_name=wizard
                )
                if imp:
                    msg = f"✅ {imp} battles imported ({skip:,} others skipped)."
                else:
                    msg = "No new siege battles found."
                self.after(0, lambda: self._finish_import(msg))
            except Exception as e:
                self.after(0, lambda: self._finish_import(f"Error: {e}", error=True))

        threading.Thread(target=run, daemon=True).start()

    def _finish_import(self, msg, error=False):
        self._import_status.config(text=msg, fg=LOSS_CLR if error else WIN_CLR)
        self._on_change()
        messagebox.showinfo("Import Complete", msg)

    def _on_change(self):
        self.defenses.refresh()
        self.offenses.refresh()
        self.battlelog.refresh()
        self.ai_tab.refresh()

if __name__ == "__main__":
    # ── License gate (bypassed in dev mode)
    import os as _os
    _dev_mode = _os.path.exists(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".devmode"))
    if not _dev_mode and not lic.is_licensed():
        gate = LicenseWindow()
        gate.mainloop()
        if not gate.activated:
            # User closed without activating
            import sys; sys.exit(0)
    # ── Launch main app
    app = SiegeApp()
    app.mainloop()
