#!/usr/bin/env python3
"""ai_organizer GUI modern (tkinter stdlib). ID/EN, tooltip ?, autostart,
multi-model LLM, allowlist belajar, warning risiko, log perubahan per tab."""
import csv
import glob
import os
import queue
import sys

sys.dont_write_bytecode = True  # jangan buat __pycache__ di folder utama
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from app.core import settings as settings_mod

LANG = settings_mod.load(BASE).get("lang", "id")

STRINGS = {
"id": {
 "title": "ai_organizer — AI Agent", "subtitle": "duplikat • broken • dokumen AI",
 "dry": "Dry-run global", "start": "▶  MULAI", "stop": "⏹ Stop", "ready": "Siap.",
 "running": "Berjalan…", "done": "Selesai.", "t_dup": "Duplikat", "t_brk": "Broken",
 "t_doc": "Dokumen AI", "t_set": "Pengaturan", "src": "Folder sumber", "pick": "Pilih…",
 "outdef": "Output default (folder ai_organizer / results/)", "outcustom": "Folder output sendiri:",
 "outis": "Isi output: duplicate/  broken/light|heavy/  dokumen/  reports/",
 "action": "Aksi", "scan": "Scan — cari saja, aman (tidak pindah/hapus).",
 "karantina": "Karantina — PINDAH ke results/duplicate/ (sisakan 1).",
 "method": "Metode", "exact": "Exact — 100% identik SHA256. Cepat, tanpa salah tuduh.",
 "visual": "Exact + visual — mirip-visual dHash. Lambat, bisa false positive.",
 "kind": "Jenis", "vbrk": "Video rusak — via ffprobe (butuh ffmpeg).",
 "ibrk": "Gambar rusak — via PIL (tanpa ffmpeg).",
 "size": "Ukuran sama — grup size PERSIS + PINDAH (khusus folder broken).",
 "brout": "Hasil broken", "copy": "Copy — original tetap (aman).",
 "move": "Move — original dipindah + verifikasi.",
 "log": "Log perubahan", "nolog": "Belum ada proses. Jalankan MULAI.",
 "warn_move": "⚠ Mode ini MEMINDAH file. Coba dry-run dulu bila ragu.",
 "confirm": "Jalankan aksi berisiko ini?",
},
"en": {
 "title": "ai_organizer — AI Agent", "subtitle": "duplicates • broken • doc AI",
 "dry": "Global dry-run", "start": "▶  START", "stop": "⏹ Stop", "ready": "Ready.",
 "running": "Running…", "done": "Done.", "t_dup": "Duplicates", "t_brk": "Broken",
 "t_doc": "Doc AI", "t_set": "Settings", "src": "Source folder", "pick": "Browse…",
 "outdef": "Default output (ai_organizer folder / results/)", "outcustom": "Custom output folder:",
 "outis": "Output contains: duplicate/  broken/light|heavy/  dokumen/  reports/",
 "action": "Action", "scan": "Scan — search only, safe (no move/delete).",
 "karantina": "Quarantine — MOVE to results/duplicate/ (keep 1).",
 "method": "Method", "exact": "Exact — 100% identical SHA256. Fast, no false positives.",
 "visual": "Exact + visual — visual-similar dHash. Slower, may false-positive.",
 "kind": "Type", "vbrk": "Broken video — via ffprobe (needs ffmpeg).",
 "ibrk": "Broken image — via PIL (no ffmpeg).",
 "size": "Same size — EXACT-size groups + MOVE (broken folders).",
 "brout": "Broken output", "copy": "Copy — original kept (safe).",
 "move": "Move — original moved + verified.",
 "log": "Change log", "nolog": "No run yet. Press START.",
 "warn_move": "⚠ This mode MOVES files. Try dry-run first if unsure.",
 "confirm": "Run this risky action?",
}}

S = STRINGS.get(LANG, STRINGS["id"])

HELP = {
"id": {
 "src": "Folder yang akan di-scan. Sub folder ikut terbaca otomatis.",
 "out": "Semua hasil (duplicate/broken/reports) dibuat di sini.",
 "action": "Scan hanya membaca. Karantina MEMINDAH duplikat (sisakan 1 per grup).",
 "method": "Exact = hash SHA256 identik 100%. Visual = tambah kemiripan gambar (pHash), bisa salah tuduh.",
 "log": "Terisi otomatis setelah proses: ringkasan + tabel file yang berubah.",
 "kind": "Video butuh ffprobe. Gambar hanya butuh Pillow. Size cocok untuk folder broken.",
 "brout": "Copy aman (original tetap). Move memindah + verifikasi (butuh admin di folder protektif).",
 "doc": "AI membaca isi dokumen lalu menyarankan kategori/nama. Koreksi via tabel agar AI belajar.",
 "apply": "Tata file ke results/dokumen/<kategori>/. Copy = original tetap.",
 "llm": "Model bahasa lokal (Ollama). Membantu file yang membingungkan + ringkasan. Butuh download model.",
 "learn": "Batasi folder yang boleh dipelajari AI. Kosongkan = semua (kecuali folder sistem).",
 "auto": "Daemon background + autostart Windows + rekomendasi otomatis.",
},
"en": {
 "src": "Folder to scan. Subfolders included automatically.",
 "out": "All outputs (duplicate/broken/reports) go here.",
 "action": "Scan only reads. Quarantine MOVES duplicates (keeps 1 per group).",
 "method": "Exact = 100% identical SHA256. Visual = image similarity (pHash), may false-positive.",
 "log": "Auto-filled after each run: summary + table of changed files.",
 "kind": "Video needs ffprobe. Images only need Pillow. Size fits broken folders.",
 "brout": "Copy is safe (original kept). Move relocates + verifies (needs admin in protected folders).",
 "doc": "AI reads document contents then suggests category/name. Correct via table so it learns.",
 "apply": "Arrange files into results/dokumen/<category>/. Copy = keep original.",
 "llm": "Local language model (Ollama). Helps confusing files + summaries. Needs model download.",
 "learn": "Limit folders the AI may learn from. Empty = all (except system folders).",
 "auto": "Background daemon + Windows autostart + automatic recommendations.",
}}

H = HELP.get(LANG, HELP["id"])

BG, BG2, BG3, FG, DIM, ACC, ACCH, OKC = (
    "#141624", "#1e2135", "#2b3050", "#eef0fa", "#9aa0b5", "#5b8cff", "#7ba2ff", "#3ddc97")
FONT_H = ("Segoe UI", 11, "bold")
FONT_S = ("Segoe UI", 10, "bold")
FONT_B = ("Segoe UI", 9)
FONT_M = ("Consolas", 9)


class ToolTip:
    def __init__(self, widget, text):
        self.w, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _e=None):
        if self.tip:
            return
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        x = self.w.winfo_rootx() + 20
        y = self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#0f111d", foreground="#ffe9a8",
                 font=("Segoe UI", 9), wraplength=320, justify="left",
                 relief="solid", borderwidth=1, padx=8, pady=6).pack()

    def hide(self, _e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def style_init(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", background=BG, foreground=FG, font=FONT_B, fieldbackground=BG2,
                 bordercolor=BG3, lightcolor=BG3, darkcolor=BG3)
    st.configure("TFrame", background=BG)
    st.configure("Card.TFrame", background=BG2, relief="flat")
    st.configure("TLabel", background=BG, foreground=FG)
    st.configure("Card.TLabel", background=BG2, foreground=FG)
    st.configure("H.TLabel", background=BG, foreground=FG, font=FONT_H)
    st.configure("S.TLabel", background=BG, foreground=ACC, font=FONT_S)
    st.configure("Dim.TLabel", background=BG, foreground=DIM)
    st.configure("CardDim.TLabel", background=BG2, foreground=DIM)
    st.configure("Warn.TLabel", background=BG, foreground="#ffb454")
    st.configure("CardWarn.TLabel", background=BG2, foreground="#ffb454")
    st.configure("Q.TButton", background=BG3, foreground="#ffe9a8", padding=(2, 1),
                 font=("Segoe UI", 8, "bold"))
    st.map("Q.TButton", background=[("active", ACC)])
    st.configure("TButton", background=BG3, foreground=FG, padding=(10, 6), borderwidth=0)
    st.map("TButton", background=[("active", ACC)], foreground=[("active", "white")])
    st.configure("Accent.TButton", background=ACC, foreground="white", font=FONT_H,
                 padding=(18, 9))
    st.map("Accent.TButton", background=[("active", "#3f6fe0"), ("disabled", BG3)])
    st.configure("TCheckbutton", background=BG, foreground=FG)
    st.configure("Card.TCheckbutton", background=BG2, foreground=FG)
    st.configure("TRadiobutton", background=BG, foreground=FG)
    st.configure("Card.TRadiobutton", background=BG2, foreground=FG)
    st.configure("TNotebook", background=BG, borderwidth=0)
    st.configure("TNotebook.Tab", background=BG2, foreground=DIM, padding=(18, 10), font=FONT_S)
    st.map("TNotebook.Tab",
           background=[("selected", ACC), ("active", ACCH)],
           foreground=[("selected", "white"), ("active", "white")],
           expand=[("selected", (2, 2, 0, 0))])
    st.configure("Treeview", background=BG2, foreground=FG, fieldbackground=BG2,
                 rowheight=24, borderwidth=0)
    st.configure("Treeview.Heading", background=BG3, foreground=FG, font=FONT_B, relief="flat")
    st.map("Treeview", background=[("selected", ACC)], foreground=[("selected", "white")])
    st.configure("Horizontal.TProgressbar", background=ACC, troughcolor=BG2, borderwidth=0)
    st.configure("TEntry", fieldbackground=BG2, foreground=FG, insertcolor=FG, borderwidth=0,
                 padding=6)
    st.configure("TCombobox", fieldbackground=BG2, foreground=FG, borderwidth=0, padding=5)
    return st


def qbutton(parent, helpkey):
    b = ttk.Button(parent, text="?", width=2, style="Q.TButton")
    ToolTip(b, H.get(helpkey, helpkey))
    return b


def reports_dir(tab):
    try:
        if not tab.use_default.get() and tab.out.get().strip():
            return os.path.join(os.path.abspath(tab.out.get().strip()), "results", "reports")
    except Exception:
        pass
    return os.path.join(BASE, "results", "reports")


def latest(pattern, folder):
    cands = glob.glob(os.path.join(folder, pattern))
    return max(cands, key=os.path.getmtime) if cands else ""


def read_duplikat(path):
    rows = []
    try:
        if path.endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                name = z.namelist()[0]
                with z.open(name) as f:
                    text = f.read().decode("utf-8-sig", "replace").splitlines()
        else:
            with open(path, encoding="utf-8-sig") as f:
                text = f.read().splitlines()
        for r in csv.DictReader(text):
            rows.append((r.get("grup", ""), r.get("status", ""), r.get("path", "")))
    except Exception:
        pass
    return rows


def read_report_csv(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


class TabBase(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.columnconfigure(0, weight=1)
        card = ttk.Frame(self, style="Card.TFrame", padding=10)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        card.columnconfigure(0, weight=1)
        hrow = ttk.Frame(card, style="Card.TFrame")
        hrow.grid(row=0, column=0, sticky="w")
        ttk.Label(hrow, text=S["src"], style="Card.TLabel", font=FONT_S).pack(side="left")
        qbutton(hrow, "src").pack(side="left", padx=6)
        self.src = tk.StringVar()
        ttk.Entry(card, textvariable=self.src, width=56).grid(row=1, column=0, sticky="ew",
                                                              padx=(0, 6), pady=(4, 2))
        ttk.Button(card, text=S["pick"], command=self.pick_src).grid(row=1, column=1)
        self.use_default = tk.BooleanVar(value=True)
        ttk.Checkbutton(card, text=S["outdef"], variable=self.use_default,
                        command=self.toggle_out, style="Card.TCheckbutton").grid(
            row=2, column=0, sticky="w", pady=(4, 0))
        orow = ttk.Frame(card, style="Card.TFrame")
        orow.grid(row=3, column=0, sticky="w")
        ttk.Label(orow, text=S["outcustom"], style="CardDim.TLabel").pack(side="left")
        qbutton(orow, "out").pack(side="left", padx=6)
        self.out = tk.StringVar()
        self.out_entry = ttk.Entry(card, textvariable=self.out, width=56, state="disabled")
        self.out_entry.grid(row=4, column=0, sticky="ew", padx=(0, 6), pady=(2, 0))
        self.out_btn = ttk.Button(card, text=S["pick"], command=self.pick_out, state="disabled")
        self.out_btn.grid(row=4, column=1)
        ttk.Label(card, text=S["outis"], style="CardDim.TLabel").grid(row=5, column=0,
                                                                      sticky="w", pady=(4, 0))
        self.row = 1

    def pick_src(self):
        d = filedialog.askdirectory(title=S["src"])
        if d:
            self.src.set(d)

    def pick_out(self):
        d = filedialog.askdirectory(title=S["outcustom"])
        if d:
            self.out.set(d)

    def toggle_out(self):
        st = "disabled" if self.use_default.get() else "normal"
        self.out_entry.config(state=st)
        self.out_btn.config(state=st)

    def base_cmd(self, mode):
        if not self.src.get().strip():
            messagebox.showwarning("!", S["src"])
            return None
        cmd = [mode, self.src.get().strip()]
        if not self.use_default.get() and self.out.get().strip():
            cmd += ["--out", self.out.get().strip()]
        if self.app.dry.get():
            cmd += ["--dry-run"]
        return cmd

    def refresh_results(self):
        """Override: isi panel Log perubahan."""

    def _log_card(self, title=None):
        card = ttk.Frame(self, style="Card.TFrame", padding=10)
        card.grid(row=self.row, column=0, sticky="nsew", pady=(8, 0))
        card.columnconfigure(0, weight=1)
        self.row += 1
        hrow = ttk.Frame(card, style="Card.TFrame")
        hrow.grid(row=0, column=0, sticky="w")
        ttk.Label(hrow, text=title or S["log"], style="Card.TLabel", font=FONT_S).pack(side="left")
        qbutton(hrow, "log").pack(side="left", padx=6)
        self.summary = ttk.Label(card, text=S["nolog"], style="CardDim.TLabel",
                                 wraplength=640, justify="left")
        self.summary.grid(row=1, column=0, sticky="w", pady=(2, 6))
        return card

    def _risky(self):
        return False


class DupTab(TabBase):
    def __init__(self, master, app):
        super().__init__(master, app)
        opt = ttk.Frame(self, padding=(2, 0))
        opt.grid(row=self.row, column=0, sticky="ew")
        self.row += 1
        self.action = tk.StringVar(value="scan")
        hrow = ttk.Frame(opt)
        hrow.pack(anchor="w", pady=(2, 2))
        ttk.Label(hrow, text=S["action"], style="H.TLabel").pack(side="left")
        qbutton(hrow, "action").pack(side="left", padx=6)
        ttk.Radiobutton(opt, text=S["scan"], value="scan", variable=self.action).pack(anchor="w")
        ttk.Radiobutton(opt, text=S["karantina"], value="karantina", variable=self.action).pack(anchor="w")
        self.warn = ttk.Label(opt, text=S["warn_move"], style="Warn.TLabel")
        self.dup = tk.StringVar(value="exact")
        hrow2 = ttk.Frame(opt)
        hrow2.pack(anchor="w", pady=(8, 2))
        ttk.Label(hrow2, text=S["method"], style="H.TLabel").pack(side="left")
        qbutton(hrow2, "method").pack(side="left", padx=6)
        ttk.Radiobutton(opt, text=S["exact"], value="exact", variable=self.dup).pack(anchor="w")
        ttk.Radiobutton(opt, text=S["visual"], value="visual", variable=self.dup).pack(anchor="w")
        self.action.trace_add("write", lambda *_: self._toggle_warn())
        self._toggle_warn()
        card = self._log_card()
        cols = ("grup", "status", "path")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=7)
        for c, w in (("grup", 60), ("status", 100), ("path", 470)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w)
        self.tree.grid(row=2, column=0, sticky="nsew")
        card.rowconfigure(2, weight=1)
        self.rowconfigure(self.row - 1, weight=1)

    def _toggle_warn(self):
        if self.action.get() == "karantina":
            self.warn.pack(anchor="w", pady=(4, 0))
        else:
            self.warn.pack_forget()

    def _risky(self):
        return self.action.get() == "karantina" and not self.app.dry.get()

    def cmd(self):
        c = self.base_cmd(self.action.get())
        if c and self.action.get() in ("scan", "karantina"):
            c += ["--mode", self.dup.get()]
        return c

    def refresh_results(self):
        rep = latest("duplikat_*.zip", reports_dir(self)) or latest("duplikat_*.csv", reports_dir(self))
        for i in self.tree.get_children():
            self.tree.delete(i)
        if not rep:
            self.summary.config(text=S["nolog"])
            return False
        rows = read_duplikat(rep)
        grups = {r[0] for r in rows}
        dup = [r for r in rows if r[1] != "disimpan"]
        self.summary.config(
            text=f"{os.path.basename(rep)} — {len(grups)} grup, {len(dup)} duplikat "
                 f"({'duplicate/' if self.action.get() == 'karantina' else 'report only'}).")
        for g, s, p in rows[:500]:
            self.tree.insert("", "end", values=(g, s, p))
        if len(rows) > 500:
            self.tree.insert("", "end", values=("", "", f"... +{len(rows) - 500}"))
        return True


class BrokenTab(TabBase):
    def __init__(self, master, app):
        super().__init__(master, app)
        opt = ttk.Frame(self, padding=(2, 0))
        opt.grid(row=self.row, column=0, sticky="ew")
        self.row += 1
        self.kind = tk.StringVar(value="video-broken")
        hrow = ttk.Frame(opt)
        hrow.pack(anchor="w", pady=(2, 2))
        ttk.Label(hrow, text=S["kind"], style="H.TLabel").pack(side="left")
        qbutton(hrow, "kind").pack(side="left", padx=6)
        ttk.Radiobutton(opt, text=S["vbrk"], value="video-broken", variable=self.kind).pack(anchor="w")
        ttk.Radiobutton(opt, text=S["ibrk"], value="image-broken", variable=self.kind).pack(anchor="w")
        ttk.Radiobutton(opt, text=S["size"], value="size", variable=self.kind).pack(anchor="w")
        self.bmode = tk.StringVar(value="copy")
        hrow2 = ttk.Frame(opt)
        hrow2.pack(anchor="w", pady=(8, 2))
        ttk.Label(hrow2, text=S["brout"], style="H.TLabel").pack(side="left")
        qbutton(hrow2, "brout").pack(side="left", padx=6)
        ttk.Radiobutton(opt, text=S["copy"], value="copy", variable=self.bmode).pack(anchor="w")
        ttk.Radiobutton(opt, text=S["move"], value="move", variable=self.bmode).pack(anchor="w")
        self.warn = ttk.Label(opt, text=S["warn_move"], style="Warn.TLabel")
        self.bmode.trace_add("write", lambda *_: self._toggle_warn())
        self.kind.trace_add("write", lambda *_: self._toggle_warn())
        self._toggle_warn()
        card = self._log_card()
        cols = ("status", "tujuan", "path")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=7)
        for c, w in (("status", 120), ("tujuan", 200), ("path", 310)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w)
        self.tree.grid(row=2, column=0, sticky="nsew")
        card.rowconfigure(2, weight=1)
        self.rowconfigure(self.row - 1, weight=1)

    def _toggle_warn(self):
        if self.bmode.get() == "move" or self.kind.get() == "size":
            self.warn.pack(anchor="w", pady=(4, 0))
        else:
            self.warn.pack_forget()

    def _risky(self):
        return (self.bmode.get() == "move" or self.kind.get() == "size") and not self.app.dry.get()

    def cmd(self):
        c = self.base_cmd(self.kind.get())
        if c and self.kind.get() in ("video-broken", "image-broken"):
            c += ["--broken-mode", self.bmode.get()]
        return c

    def refresh_results(self):
        folder = reports_dir(self)
        rep = (latest("video_report_*.csv", folder) if self.kind.get() == "video-broken"
               else latest("image_report_*.csv", folder) if self.kind.get() == "image-broken"
               else latest("size_*.csv", folder))
        for i in self.tree.get_children():
            self.tree.delete(i)
        if not rep:
            self.summary.config(text=S["nolog"])
            return False
        rows = read_report_csv(rep)
        if self.kind.get() == "size":
            n = sum(1 for r in rows if r.get("status") != "disimpan")
            self.summary.config(text=f"{os.path.basename(rep)} — {n} same-size files → duplicate/.")
            for r in rows[:500]:
                self.tree.insert("", "end", values=(r.get("status"), "duplicate/", r.get("path")))
        else:
            by = {}
            for r in rows:
                by[r.get("status", "?")] = by.get(r.get("status", "?"), 0) + 1
            self.summary.config(text=f"{os.path.basename(rep)} — " +
                                     ", ".join(f"{k}: {v}" for k, v in sorted(by.items())))
            for r in rows:
                if r.get("status") in ("LIGHT_BROKEN", "HEAVY_BROKEN"):
                    self.tree.insert("", "end", values=(r.get("status"), r.get("copied_to", ""),
                                                        r.get("path", "")))
                    if len(self.tree.get_children()) >= 500:
                        break
        return True


class DocTab(TabBase):
    def __init__(self, master, app):
        super().__init__(master, app)
        opt = ttk.Frame(self, padding=(2, 0))
        opt.grid(row=self.row, column=0, sticky="ew")
        self.row += 1
        hrow = ttk.Frame(opt)
        hrow.pack(anchor="w", pady=(2, 4))
        ttk.Label(hrow, text="Dokumen AI", style="H.TLabel").pack(side="left")
        qbutton(hrow, "doc").pack(side="left", padx=6)
        self.apply = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="Apply: arrange → results/dokumen/<kategori>/",
                        variable=self.apply).pack(anchor="w")
        self.apply_copy = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="Copy only (keep original)", variable=self.apply_copy).pack(anchor="w")
        self.warn = ttk.Label(opt, text=S["warn_move"], style="Warn.TLabel")
        self.apply.trace_add("write", lambda *_: self._toggle_warn())
        self.apply_copy.trace_add("write", lambda *_: self._toggle_warn())
        self._toggle_warn()
        fr = ttk.Frame(opt)
        fr.pack(anchor="w", pady=(6, 0))
        ttk.Label(fr, text="Limit (0 = all):").pack(side="left")
        self.limit = tk.StringVar(value="0")
        ttk.Entry(fr, textvariable=self.limit, width=8).pack(side="left", padx=6)
        self.use_llm = tk.BooleanVar(value=False)
        hrow2 = ttk.Frame(opt)
        hrow2.pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(hrow2, text="Local LLM Qwen (~5s/file)", variable=self.use_llm).pack(side="left")
        qbutton(hrow2, "llm").pack(side="left", padx=6)
        card = self._log_card()
        cols = ("kategori", "conf", "saran", "nama")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=7)
        for col, w in zip(cols, (110, 60, 170, 290)):
            self.tree.heading(col, text={"kategori": "Kategori", "conf": "Conf",
                                         "saran": "Saran folder", "nama": "Saran nama"}[col])
            self.tree.column(col, width=w)
        self.tree.grid(row=2, column=0, sticky="nsew")
        card.rowconfigure(2, weight=1)
        fr2 = ttk.Frame(card)
        fr2.grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Label(fr2, text="Koreksi:").pack(side="left")
        self.fix = ttk.Combobox(fr2, width=14, state="readonly",
                                values=["Keuangan", "Akademik", "Kantor", "Hukum",
                                        "Kesehatan", "Teknologi", "Pribadi", "Lainnya"])
        self.fix.pack(side="left", padx=6)
        ttk.Button(fr2, text="Belajar!", command=self.learn).pack(side="left")
        self.rowconfigure(self.row - 1, weight=1)
        self._paths = {}

    def _toggle_warn(self):
        if self.apply.get() and not self.apply_copy.get():
            self.warn.pack(anchor="w", pady=(4, 0))
        else:
            self.warn.pack_forget()

    def _risky(self):
        return self.apply.get() and not self.apply_copy.get() and not self.app.dry.get()

    def cmd(self):
        c = self.base_cmd("analyze")
        if not c:
            return None
        try:
            lim = int(self.limit.get() or "0")
        except ValueError:
            lim = 0
        if lim > 0:
            c += ["--limit", str(lim)]
        if self.use_llm.get():
            c += ["--llm"]
            try:
                sys.path.insert(0, BASE)
                from app.core import settings as settings_mod
                m = settings_mod.load(BASE).get("llm_model", "")
                if m:
                    c += ["--llm-model", m]
            except Exception:
                pass
        if self.apply.get():
            c += ["--apply"]
            if self.apply_copy.get():
                c += ["--apply-copy"]
        return c

    def refresh_results(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._paths.clear()
        rep = latest("doc_report_*.csv", reports_dir(self))
        if not rep:
            self.summary.config(text=S["nolog"])
            return False
        rows = read_report_csv(rep)
        cats = {}
        for r in rows:
            cats[r.get("kategori", "?")] = cats.get(r.get("kategori", "?"), 0) + 1
        self.summary.config(text=f"{os.path.basename(rep)} — {len(rows)} files: " +
                                 ", ".join(f"{k} {v}" for k, v in sorted(cats.items(), key=lambda x: -x[1])))
        for r in rows[:500]:
            iid = self.tree.insert("", "end", values=(r.get("kategori"), r.get("confidence"),
                                                      r.get("saran_folder"), r.get("saran_nama")))
            self._paths[iid] = r.get("path")
        return True

    def learn(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("?", "Pilih dulu baris di tabel hasil.")
            return
        cat = self.fix.get()
        if not cat:
            messagebox.showinfo("?", "Pilih kategori koreksi dulu.")
            return
        sys.path.insert(0, BASE)
        from app.ai import docai
        from app.core import settings as settings_mod
        st = settings_mod.load(BASE)
        p = self._paths.get(sel[0], "")
        if not settings_mod.learn_allowed(p, st):
            messagebox.showwarning("Izin", "Folder ini di luar izin belajar AI.\nUbah di Pengaturan → Izin belajar.")
            return
        out_root = self.out.get().strip() if (not self.use_default.get() and self.out.get().strip()) else BASE
        fb_path = os.path.join(out_root, "results", "reports", "doc_feedback.json")
        try:
            text, _ = docai.extract_text(p)
        except Exception:
            text = ""
        n = docai.save_feedback(fb_path, text or p, cat)
        messagebox.showinfo("Belajar", f"Tersimpan! AI belajar dari {n} koreksi.")


class SettingsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.columnconfigure(0, weight=1)
        st = settings_mod_load()
        # --- AI ---
        card = ttk.Frame(self, style="Card.TFrame", padding=10)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        hrow = ttk.Frame(card, style="Card.TFrame")
        hrow.pack(anchor="w")
        ttk.Label(hrow, text="Kekuatan reasoning", style="Card.TLabel", font=FONT_S).pack(side="left")
        qbutton(hrow, "auto").pack(side="left", padx=6)
        self.level = tk.StringVar(value=str(st.get("reason_level", 2)))
        for v, desc in (("1", "L1 cepat — nama & atribut (~1ms/file)."),
                        ("2", "L2 standar — + isi dokumen/gambar (disarankan)."),
                        ("3", "L3 mendalam — + LLM lokal (lambat, paling pintar).")):
            ttk.Radiobutton(card, text=desc, value=v, variable=self.level,
                            style="Card.TRadiobutton").pack(anchor="w")
        fr = ttk.Frame(card, style="Card.TFrame")
        fr.pack(anchor="w", pady=(6, 0))
        ttk.Label(fr, text="Maks file LLM:", style="Card.TLabel").pack(side="left")
        self.llm_max = tk.StringVar(value=str(st.get("llm_max", 20)))
        ttk.Entry(fr, textvariable=self.llm_max, width=6).pack(side="left", padx=6)
        # --- model ---
        mrow = ttk.Frame(card, style="Card.TFrame")
        mrow.pack(anchor="w", pady=(6, 0))
        ttk.Label(mrow, text="Model LLM:", style="Card.TLabel").pack(side="left")
        qbutton(mrow, "llm").pack(side="left", padx=6)
        self.model = tk.StringVar(value=st.get("llm_model", "qwen2.5:0.5b"))
        self.model_cb = ttk.Combobox(mrow, textvariable=self.model, width=52, state="readonly",
                                     values=_model_labels())
        self.model_cb.pack(side="left", padx=6)
        brow = ttk.Frame(card, style="Card.TFrame")
        brow.pack(anchor="w", pady=(4, 0))
        ttk.Button(brow, text="Download model", command=self.dl_model).pack(side="left")
        ttk.Button(brow, text="Jadikan aktif", command=self.set_model).pack(side="left", padx=6)
        ttk.Button(fr, text="Simpan", command=self.save).pack(side="left", padx=12)
        # --- izin belajar ---
        card2 = ttk.Frame(self, style="Card.TFrame", padding=10)
        card2.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        hrow2 = ttk.Frame(card2, style="Card.TFrame")
        hrow2.pack(anchor="w")
        ttk.Label(hrow2, text="Izin belajar AI (dokumen/folder)", style="Card.TLabel",
                  font=FONT_S).pack(side="left")
        qbutton(hrow2, "learn").pack(side="left", padx=6)
        ttk.Label(card2, text="Kosongkan = semua boleh kecuali folder sistem.",
                  style="CardDim.TLabel").pack(anchor="w")
        lrow = ttk.Frame(card2, style="Card.TFrame")
        lrow.pack(fill="x", pady=(4, 0))
        self.allow_lb = tk.Listbox(lrow, height=3, bg=BG, fg=FG, relief="flat",
                                   selectmode="extended")
        self.allow_lb.pack(side="left", fill="x", expand=True)
        for a in st.get("learn_folders", []):
            self.allow_lb.insert("end", a)
        lbtn = ttk.Frame(lrow, style="Card.TFrame")
        lbtn.pack(side="left", padx=6)
        ttk.Button(lbtn, text="+ Boleh", command=lambda: self._add_rm(self.allow_lb, True)).pack(fill="x")
        ttk.Button(lbtn, text="− Hapus", command=lambda: self._add_rm(self.allow_lb, False)).pack(fill="x", pady=4)
        erow = ttk.Frame(card2, style="Card.TFrame")
        erow.pack(fill="x", pady=(4, 0))
        ttk.Label(erow, text="Jangan pelajari:", style="Card.TLabel").pack(anchor="w")
        self.deny_lb = tk.Listbox(erow, height=3, bg=BG, fg=FG, relief="flat",
                                  selectmode="extended")
        self.deny_lb.pack(side="left", fill="x", expand=True)
        for a in st.get("learn_exclude", []):
            self.deny_lb.insert("end", a)
        dbtn = ttk.Frame(erow, style="Card.TFrame")
        dbtn.pack(side="left", padx=6)
        ttk.Button(dbtn, text="+ Larang", command=lambda: self._add_rm(self.deny_lb, True)).pack(fill="x")
        ttk.Button(dbtn, text="− Hapus", command=lambda: self._add_rm(self.deny_lb, False)).pack(fill="x", pady=4)
        ttk.Button(card2, text="Simpan izin", command=self.save_learn).pack(anchor="w", pady=(6, 0))
        # --- autostart ---
        card3 = ttk.Frame(self, style="Card.TFrame", padding=10)
        card3.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        hrow3 = ttk.Frame(card3, style="Card.TFrame")
        hrow3.pack(anchor="w")
        ttk.Label(hrow3, text="Otomatis background", style="Card.TLabel", font=FONT_S).pack(side="left")
        qbutton(hrow3, "auto").pack(side="left", padx=6)
        self.auto_status = ttk.Label(card3, text="…", style="CardDim.TLabel")
        self.auto_status.pack(anchor="w", pady=(2, 4))
        arow = ttk.Frame(card3, style="Card.TFrame")
        arow.pack(anchor="w")
        ttk.Button(arow, text="Aktifkan autostart", command=lambda: self._auto(True)).pack(side="left")
        ttk.Button(arow, text="Matikan", command=lambda: self._auto(False)).pack(side="left", padx=6)
        ttk.Button(arow, text="Refresh status", command=self.refresh_auto).pack(side="left", padx=6)
        self.refresh_auto()
        # --- bahasa + rekomendasi ---
        card4 = ttk.Frame(self, style="Card.TFrame", padding=10)
        card4.grid(row=3, column=0, sticky="ew")
        lrow2 = ttk.Frame(card4, style="Card.TFrame")
        lrow2.pack(anchor="w")
        ttk.Label(lrow2, text="Bahasa / Language:", style="Card.TLabel").pack(side="left")
        self.lang = tk.StringVar(value=settings_mod_load().get("lang", "id"))
        ttk.Combobox(lrow2, textvariable=self.lang, width=12, state="readonly",
                     values=["id", "en"]).pack(side="left", padx=6)
        ttk.Button(lrow2, text="Simpan (restart)", command=self.save_lang).pack(side="left", padx=6)
        ttk.Button(card4, text="Lihat rekomendasi",
                   command=lambda: self.app.run_raw(["--recommend"])).pack(anchor="w", pady=(6, 0))
        ttk.Label(card4, text="⚠ Fitur PINDAH/Move menghapus dari lokasi asal (terverifikasi). "
                              "Dry-run dulu bila ragu. Uninstall tidak menghapus results/.",
                  style="CardWarn.TLabel", wraplength=620, justify="left").pack(anchor="w", pady=(6, 0))

    def save(self):
        st = settings_mod_load()
        try:
            st["reason_level"] = int(self.level.get())
            st["llm_max"] = int(self.llm_max.get() or "20")
        except ValueError:
            pass
        settings_mod_save(st)
        messagebox.showinfo("OK", "Tersimpan.")

    def set_model(self):
        st = settings_mod_load()
        st["llm_model"] = self.model.get().split(" — ")[0]
        settings_mod_save(st)
        messagebox.showinfo("OK", f"Model aktif: {st['llm_model']}")

    def dl_model(self):
        m = self.model.get().split(" — ")[0]
        if messagebox.askokcancel("Download",
                                  f"Download {m} (~ukuran di label)?\nButuh internet + Ollama."):
            self.app.run_ollama_pull(m)

    def _add_rm(self, lb, add):
        if add:
            d = filedialog.askdirectory(title="Pilih folder")
            if d:
                lb.insert("end", d)
        else:
            for i in sorted(lb.curselection(), reverse=True):
                lb.delete(i)

    def save_learn(self):
        st = settings_mod_load()
        st["learn_folders"] = list(self.allow_lb.get(0, "end"))
        st["learn_exclude"] = list(self.deny_lb.get(0, "end"))
        settings_mod_save(st)
        messagebox.showinfo("OK", "Izin belajar tersimpan.")

    def save_lang(self):
        st = settings_mod_load()
        st["lang"] = self.lang.get()
        settings_mod_save(st)
        messagebox.showinfo("OK", "Restart aplikasi untuk ganti bahasa.")

    def _auto(self, on):
        sys.path.insert(0, BASE)
        from app.core import engine
        if on:
            if engine.is_installed(BASE):
                messagebox.showinfo("OK", "Sudah aktif.")
                self.refresh_auto()
                return
            self.app.run_raw_engine_fn(engine.do_install, [])
        else:
            if not engine.is_installed(BASE):
                messagebox.showinfo("OK", "Sudah mati.")
                self.refresh_auto()
                return
            self.app.run_raw_engine_fn(engine.do_uninstall, None)

    def refresh_auto(self):
        on, n = autostart_state()
        self.auto_status.config(
            text=f"Autostart: {'ON' if on else 'OFF'} • Daemon: "
                 f"{'berjalan (%d)' % n if n else 'tidak berjalan'} • "
                 f"Belajar: selalu aktif di background saat daemon jalan.")


def settings_mod_load():
    sys.path.insert(0, BASE)
    from app.core import settings as settings_mod
    return settings_mod.load(BASE)


def settings_mod_save(st):
    sys.path.insert(0, BASE)
    from app.core import settings as settings_mod
    settings_mod.save(BASE, st)


def _model_labels():
    try:
        sys.path.insert(0, BASE)
        from app.ai import llm
        return [f"{m} — {label}" for m, label, _ram, _sz in llm.MODELS]
    except Exception:
        return ["qwen2.5:0.5b"]


def autostart_state():
    """(startup_on, daemon_procs)."""
    on, n = False, 0
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                try:
                    winreg.QueryValueEx(k, "ai_organizer")
                    on = True
                except OSError:
                    pass
        except Exception:
            pass
        try:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq organizer-cli.exe"],
                                 capture_output=True, text=True, timeout=15,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            n = sum(1 for line in out.splitlines() if "organizer-cli.exe" in line)
        except Exception:
            pass
    return on, n


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(S["title"])
        self.geometry("800x780")
        self.configure(bg=BG)
        self._set_icon()
        style_init(self)
        self.q = queue.Queue()
        self._busy = False
        self.dry = tk.BooleanVar(value=False)
        top = ttk.Frame(self, padding=(14, 10, 14, 0))
        top.pack(fill="x")
        ttk.Label(top, text="◈ ai_organizer", style="H.TLabel").pack(side="left")
        ttk.Label(top, text=S["subtitle"], style="Dim.TLabel").pack(side="left", padx=10)
        ttk.Checkbutton(top, text=S["dry"], variable=self.dry).pack(side="right")
        hrow = ttk.Frame(self, padding=(14, 0, 14, 0))
        hrow.pack(fill="x")
        ttk.Label(hrow, text="AI background: pelajari + rekomendasikan terus-menerus saat daemon/autostart ON.",
                  style="Dim.TLabel").pack(side="left")
        qbutton(hrow, "auto").pack(side="left", padx=6)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=14, pady=10)
        self.t_dup = DupTab(self.nb, self)
        self.t_brk = BrokenTab(self.nb, self)
        self.t_doc = DocTab(self.nb, self)
        self.t_set = SettingsTab(self.nb, self)
        for tab, key in ((self.t_dup, "t_dup"), (self.t_brk, "t_brk"),
                         (self.t_doc, "t_doc"), (self.t_set, "t_set")):
            tab.pack(fill="both", expand=True, padx=10, pady=10)
            self.nb.add(tab, text=f"  {S[key]}  ")
        bot = ttk.Frame(self, padding=(14, 0, 14, 14))
        bot.pack(fill="both", expand=True)
        btns = ttk.Frame(bot)
        btns.pack(fill="x")
        self.start_btn = ttk.Button(btns, text=S["start"], style="Accent.TButton", command=self.start)
        self.start_btn.pack(side="left")
        ttk.Button(btns, text=S["stop"], command=self.stop).pack(side="left", padx=8)
        self.status = ttk.Label(btns, text=S["ready"], style="Dim.TLabel")
        self.status.pack(side="left", padx=12)
        self.prog = ttk.Progressbar(btns, mode="indeterminate", length=140)
        self.prog.pack(side="right")
        self.log = scrolledtext.ScrolledText(bot, height=9, bg=BG2, fg=FG, relief="flat",
                                             insertbackground=FG, font=FONT_M)
        self.log.pack(fill="both", expand=True, pady=(8, 0))
        self.log.config(state="disabled")
        self.after(100, self.pump)
        self.last_report = ""

    def _set_icon(self):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ai_organizer.app")
        except Exception:
            pass
        for name in ("icon.png", "icon.ico"):
            p = os.path.join(BASE, name)
            if os.path.isfile(p):
                try:
                    img = tk.PhotoImage(file=p)
                    self.iconphoto(True, img)
                    self._icon_ref = img
                    return
                except Exception:
                    continue

    def cur_tab(self):
        return self.nb.nametowidget(self.nb.select())

    def set_busy(self, busy, msg=""):
        self._busy = busy
        self.start_btn.config(state="disabled" if busy else "normal")
        if busy:
            self.prog.start(12)
        else:
            self.prog.stop()
        if msg:
            self.status.config(text=msg)

    def run_raw(self, argv):
        if self._busy:
            messagebox.showinfo("!", S["running"])
            return
        self.append("$ organizer " + " ".join(argv) + "\n")
        self.last_report = ""
        threading.Thread(target=self.run_engine, args=(argv,), daemon=True).start()

    def run_ollama_pull(self, model):
        if self._busy:
            messagebox.showinfo("!", S["running"])
            return
        import subprocess as _sp
        env = dict(os.environ)
        env.setdefault("OLLAMA_MODELS", os.path.join(BASE, "llm", "models"))
        self.append(f"$ ollama pull {model}\n")
        threading.Thread(target=self._pull, args=(model, env), daemon=True).start()

    def _pull(self, model, env):
        import subprocess as _sp
        self.after(0, lambda: self.set_busy(True, "Download…"))
        try:
            p = _sp.Popen(["ollama", "pull", model], stdout=_sp.PIPE, stderr=_sp.STDOUT,
                          text=True, errors="replace", bufsize=1, env=env,
                          creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
            for line in p.stdout:
                self.q.put(line)
            p.wait()
            self.q.put(f"[pull selesai: {model}]\n")
        except FileNotFoundError:
            self.q.put("[ollama tidak ditemukan — install via Pengaturan]\n")
        except Exception as e:
            self.q.put(f"[pull gagal: {e}]\n")
        finally:
            self.q.put(None)

    def run_raw_engine_fn(self, fn, arg):
        if self._busy:
            messagebox.showinfo("!", S["running"])
            return
        self.append(f"$ {getattr(fn, '__name__', fn)}\n")
        self.last_report = ""
        threading.Thread(target=self.run_fn, args=(fn, arg), daemon=True).start()

    def start(self):
        if self._busy:
            messagebox.showinfo("!", S["running"])
            return
        tab = self.cur_tab()
        if isinstance(tab, SettingsTab):
            messagebox.showinfo("!", "Settings")
            return
        argv = tab.cmd() if hasattr(tab, "cmd") else None
        if not argv:
            return
        if hasattr(tab, "_risky") and tab._risky():
            if not messagebox.askokcancel("⚠", S["warn_move"] + "\n\n" + S["confirm"]):
                return
        self.append("$ organizer " + " ".join(f'"{c}"' if " " in c else c for c in argv) + "\n")
        self.last_report = ""
        threading.Thread(target=self.run_engine, args=(argv,), daemon=True).start()

    def run_engine(self, argv):
        import io as _io
        import contextlib as _ctx
        sys.path.insert(0, BASE)
        from app.core import engine
        buf = _io.StringIO()
        self.after(0, lambda: self.set_busy(True, S["running"]))
        try:
            with _ctx.redirect_stdout(buf):
                engine.main(list(argv))
        except SystemExit:
            pass
        except Exception as e:
            buf.write(f"\nERROR: {e}\n")
        finally:
            out = buf.getvalue()
            for line in out.splitlines(keepends=True):
                if "Laporan:" in line:
                    self.last_report = line.split("Laporan:", 1)[1].strip()
                self.q.put(line)
            self.q.put(None)

    def run_fn(self, fn, arg):
        import io as _io
        import contextlib as _ctx
        buf = _io.StringIO()
        self.after(0, lambda: self.set_busy(True, S["running"]))
        try:
            with _ctx.redirect_stdout(buf):
                fn(arg) if arg is not None else fn()
        except SystemExit:
            pass
        except Exception as e:
            buf.write(f"\nERROR: {e}\n")
        finally:
            for line in buf.getvalue().splitlines(keepends=True):
                self.q.put(line)
            self.q.put(None)

    def pump(self):
        try:
            while True:
                line = self.q.get_nowait()
                if line is None:
                    self.set_busy(False, S["done"])
                    self.append("--- selesai ---\n")
                    tab = self.cur_tab()
                    try:
                        if hasattr(tab, "refresh_results"):
                            tab.refresh_results()
                        if self.last_report.endswith(".csv") and "doc_report" in self.last_report:
                            self.t_doc.refresh_results()
                    except Exception as e:
                        self.append(f"[panel hasil: {e}]\n")
                    break
                self.append(line)
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def append(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")

    def stop(self):
        if self._busy:
            self.append("[in-process: tunggu hingga selesai]\n")


if __name__ == "__main__":
    App().mainloop()
