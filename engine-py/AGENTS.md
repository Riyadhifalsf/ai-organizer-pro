# AGENTS.md — Prompt Tugas untuk AI yang mengerjakan ai_organizer

> File ini DIBACA AI (asisten kode / LLM lokal) sebelum mengubah apa pun.
> Manusia baca CARA_PAKAI.txt. AI baca file ini + CARA_PAKAI.txt.

## 1. Apa aplikasi ini

`ai_organizer` = AI agent kecil, **lokal 100%** (tanpa remote, tanpa internet wajib),
untuk merapikan file Windows sehari-hari: duplikat, file rusak (video/gambar),
dan dokumen (pahami isi → kategori → rekomendasi nama/folder). Target: kuat,
ringan, aman (tidak pernah menghapus tanpa perintah eksplisit dan verifikasi).

## 2. Struktur yang WAJIB dijaga

```
D:\ai-organizer-pro\            <- APP ROOT (jangan pindah/rename)
  engine-py/organizer.py        <- LAUNCHER tipis. HANYA: install|hapus|cli|gui
                                   (gui = buka qt/build/AIOrganizerPro.exe)
  qt/                           <- GUI Qt6 (app_gui.py tkinter dihapus 2026-09-22)
  icon.png / icon.ico / CARA_PAKAI.txt / AGENTS.md (file ini)
  app\
    core\engine.py               <- SELURUH engine (jangan taruh logika di launcher!)
    core\bootstrap.py            <- cek pip (pillow, watchdog); TANPA auto-install
    core\settings.py             <- settings JSON + learn_allowed()
    ai\docai.py                  <- TF-IDF + centroid + SimHash (stdlib saja!)
    ai\llm.py                    <- klien Ollama (stdlib urllib), MODELS terdaftar
    ai\reason.py                 <- reasoning L1/L2/L3 + cache
    ai\behavior.py               <- JSON perilaku (behavior.jsonl) + recommend()
    ai\jobs.py                   <- antrean JSON (jobs.json)
    ai\unified.py                <- doc_index JSON (tanpa SQLite)
    integrations\explorer.py     <- COM shellex, helper, startup, shortcut, toast
    scripts\daemon.py            <- background (watchdog + poll Explorer)
    scripts\uninstall.py         <- uninstall.exe
    native\*.cs + bin\          <- AiShExt.dll (COM), AiHelper.exe (C#, csc)
    ffmpeg\bin\                  <- ffmpeg.exe + ffprobe.exe (JANGAN hapus ffprobe!)
    config\settings.json         <- pengaturan user (jangan timpa tanpa baca dulu)
    llm\models\                  <- model Ollama (boleh kosong di repo)
  results\                       <- OUTPUT (jangan taruh kode di sini!)
    duplicate\  broken\light|heavy\  dokumen\<kat>\  reports\
```

Aturan path: JANGAN hardcode `D:\ai_organizer`. Pakai walk-up ke `organizer.py`
(`engine._app_base`, `explorer._app_root/_exe_root`). Frozen EXE: output default
di sebelah EXE (root aplikasi, BUKAN dist/ — tidak ada lagi folder dist/).

## 3. Kontrak perilaku (dilarang melanggar)

1. **Tidak ada hapus/pindah tanpa verifikasi**: setiap move wajib cek source hilang
   + ukuran dest sama (`_move_with_permission_retry` + assert). Gagal → catat, lanjut.
2. **Broken default = copy** (`--broken-mode copy`). Move hanya bila user eksplisit.
3. **`--dry-run` selalu tersedia** dan tidak menulis hasil (laporan boleh).
4. **Satu proses per out_root** (`DirLock` + `.ai_organizer.lock`). Jangan bypass.
5. **Jangan scan folder output sendiri** (skip `duplicate/`, `broken/`, `results/`,
   `duplikat/` legacy, `video_broken_detection/`).
6. **Izin belajar**: hormati `settings.learn_allowed()` untuk LLM/feedback/daemon.
   Folder sistem (Windows, Program Files, $Recycle) TIDAK PERNAH dipelajari.
7. **Jujur soal AI**: ini ML klasik + Qwen kecil. DILARANG mengklaim deep learning /
   akurasi yang tidak diukur. Confidence < 0.3 → jangan sarankan rename.
8. **Backward compat CLI**: `cli scan|karantina|video-broken|image-broken|size|analyze`
   + flag lama tetap jalan. Launcher hanya `install|hapus|cli|gui`.
9. **Stdlib-first**: dependensi pip baru HARUS didaftarkan di `bootstrap.REQUIRED`
   dan dibundel ke EXE (`--hidden-import`). Tanpa itu EXE rusak (kasus watchdog).
10. **Registry hanya HKCU** (tanpa admin): context-menu, Run, CLSID, ProgId.

## 4. Cara build & uji (wajib tiap ubah kode)

```powershell
python -m py_compile <file diubah>                       # cepat
python organizer.py cli scan D:\results\Screenshots      # uji engine
python organizer.py cli analyze D:\results\Documents --limit 5
python organizer.py gui                                  # buka aplikasi Qt
# (organizer-cli.exe frozen dihapus 2026-09-22; Qt memakai source sidecar.)
```

Catatan build: JANGAN pakai pipe Unix (`tail`, `&&`, `grep`) — shell-nya
PowerShell 5.1. Gunakan `Select-Object -First N`. Jangan `Select-Object -First`
di tengah run panjang (pipe tertutup → crash menulis).

## 5. Peta fitur → file (biar tidak salah tempat)

| Fitur | File : fungsi |
|---|---|
| Duplikat exact (size→1MB→SHA256) | core/engine.py : scan, report, karantina |
| Visual dHash (PIL murni) | core/engine.py : scan_visual, group_visual |
| Size-sama | core/engine.py : size_groups |
| Video rusak | core/engine.py : video_broken, _video_status, _find_ffprobe |
| Gambar rusak | core/engine.py : image_broken, _image_status |
| Dokumen AI | ai/docai.py : analyze_folder, classify, simhash64 |
| LLM lokal | ai/llm.py : MODELS, ensure_server, analyze_doc |
| Reasoning L1-L3 | ai/reason.py : Reasoner |
| Perilaku/rekomendasi | ai/behavior.py : Behavior |
| Explorer/COM/toast/startup | integrations/explorer.py |
| Daemon | app/scripts/daemon.py |
| GUI | qt/ (Qt6, lihat docs/QT_APP.md) + core/settings.py |
| Uninstall | app/scripts/uninstall.py + core/engine.py do_uninstall |

## 6. Batasan yang diketahui (jangan diulang kesalahannya)

- EXE frozen: `__file__` → temp `_MEI`; pip tidak bisa; `sys.path` manipulasi diabaikan
  → pakai package absolut `app.*` + `__init__.py` di tiap folder.
- ttk style: `H.TLabel` VALID, `TLabel.H` CRASH. Cek tiap tambah style.
- GUI jalan in-process + redirect stdout; JANGAN subprocess ke engine.
- `Select-Object -First N` memutus pipe → hanya untuk output pendek.
- PowerShell 5.1: tidak ada `&&`, `tail`, `grep`, `head`. Ada `Select-String`.
- Model LLM di `%OLLAMA_MODELS%` atau `llm/models`; C: sempit (2.8GB) → simpan di D:.
- Overlay icon Explorer JANGAN dipakai (slot sistem 15, habis oleh OneDrive).
