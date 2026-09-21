# AIOrganizerPro 0.3.0 — SATU folder gabungan

Penggabungan **ai_organizer** (Python: dokumen AI, LLM lokal, broken-video,
daemon, Explorer) + **AIOrganizer** (C++: scanner 1700 f/s, hash bertahap,
SQLite WAL) + master documentation (4805 baris) menjadi satu aplikasi.
Sumber lama yang redundan sudah dihapus; `ai_organizer/results/` (data user)
sengaja dipertahankan.

## Struktur final

```
ai-organizer-pro\
  AIOrganizerPro.exe  APLIKASI Windows native (Tauri+Rust) — klik 2x langsung jalan
  AIOrganizerPro-web.exe  launcher mode website (server + browser, tanpa console)
  aiorganizer.exe     core C++ (scan/duplikat/jobs/proposal/audit/doctor)
  organizer-cli.exe   engine Python beku (scan/karantina/analyze LLM)
  ai-yolo-project/    KLASIFIKASI YOLO (kanonis, jangan diubah): train.py/run.py/config.py + runs/*/best.pt
  engine-py/app/ai/yolo_bridge.py  jembatan organizer -> YOLO (mode: yolo-classify, dry-run default)
  PRO.cmd             dispatcher: gui|stats|scan|dup|doctor|migrate|db|build
  scripts/            run-server, db-stats/query/shell, scan, duplicates,
                      build-core, migrate, install-startup, doctor (.ps1)
  src/                core C++ (scanner, hashing, database v4, duplicate)
  engine-py/          engine Python (AI, LLM, broken, daemon) + sidecar.py
  gui/                GUI web modern — HTML/CSS/JS murni
  server/             bridge REST Node stdlib (port 8471)
  src-tauri/          backend Rust/Tauri v2 + icons (dari assets\icon)
  assets/             icon.ico / icon.png resmi
  docs/               MASTER doc, ARCHITECTURE, BUILD, CARA_PAKAI, AGENTS
  db/                 schema_v4.sql — SATU database terpadu
  data/               aiorganizer.db + db.json (saklar) + activity.log
  ai_organizer/results/  DATA USER lama (120GB, jangan hapus sembarangan)
  tools/              migrate_unified.py + launcher\ (sumber AIOrganizerPro-web.exe)
  tests/              GoogleTest (20 test hijau)
```

## Pakai

```powershell
.\AIOrganizerPro.exe      # APLIKASI native — klik 2x
PRO.cmd gui                 # buka GUI modern (mode website)
PRO.cmd doctor              # cek kesehatan (node/python/db/exe/ffmpeg/icon)
PRO.cmd scan D:\Data        # scan cepat (baca saja)
PRO.cmd dup D:\Data         # cari duplikat exact
PRO.cmd db "SELECT ..."     # query baca ke DB terpadu
PRO.cmd build               # rebuild core + ctest + refresh aiorganizer.exe
```

## Kontrak aman (dari CARA_PAKAI + AGENTS + MASTER doc)

Tidak pernah menghapus. Move hanya yg disetujui + verifikasi + rollback log.
Broken default copy. Dry-run tersedia. Registry hanya HKCU. AI hanya pengusul
(confidence<0.3 = tanpa saran rename), engine deterministik yang mengeksekusi.
Detail: `docs\`.
