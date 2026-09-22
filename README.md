# AIOrganizerPro 0.4.0 — aplikasi desktop Qt6/C++

```
ai-organizer-pro\
  qt\build\AIOrganizerPro.exe  APLIKASI desktop Qt6 — klik 2x langsung jalan
  qt/                 sumber GUI Qt (MainWindow, tab, player, viewer, gallery)
  src/                core C++ (scanner, hashing, database v4, duplicate, jobs)
  aiorganizer.exe     core C++ jadi (dipakai Qt via QProcess --json)
  engine-py/          HANYA AI: sidecar.py (YOLO classify/training, analyze,
                      organize, broken) — dipanggil Qt, bukan website
  ai-yolo-project/    training + bobot YOLO (jangan diubah strukturnya)
  PRO.cmd             dispatcher: gui|stats|scan|dup|doctor|migrate|db|build|build-qt
  scripts/            db-stats/query/shell, scan, duplicates, build-core,
                      build-qt, migrate, install-startup, doctor (.ps1)
  data/               aiorganizer.db + db.json (saklar) + activity.log
  db/                 schema_v4.sql — SATU database terpadu
  docs/               dokumentasi (MASTER, ARCHITECTURE, BUILD, YOLO, QT)
  tools/              migrate_unified.py
  tests/              GoogleTest
  _archive/           web stack lama (gui/server/src-tauri) + cadangan lain
```

Butuh Qt 6.8.x MSVC2022 di `D:\Qt\6.8.3\msvc2022_64` (atau set `QT_PREFIX`).
ffmpeg/ffprobe taruh manual di `engine-py/app/ffmpeg/bin/`.

Pemula mulai dari `docs/PANDUAN_PEMULA.md` (5 menit).

## Pakai

```powershell
PRO.cmd gui                 # buka aplikasi desktop Qt
PRO.cmd build-qt            # rebuild aplikasi Qt
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
