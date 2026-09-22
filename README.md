# AIOrganizerPro 0.4.0 — aplikasi desktop Qt6/C++

```
ai-organizer-pro\
  qt\build\AIOrganizerPro.exe  APLIKASI desktop Qt6 — klik 2x langsung jalan
  qt/                 sumber GUI Qt (MainWindow, tab, player, viewer, gallery)
  src/                core C++ (scanner, hashing, database v4, duplicate, jobs)
  aiorganizer.exe     core C++ jadi (dipakai Qt via QProcess --json)
  app/                Python AI: ai/ (YOLO classify/training, analyze, organize,
                      broken, jobs, behavior) + core/ (engine) — dipanggil Qt
  organizer.py + sidecar.py  launcher & jembatan JSON di root
  app/ai/yolo/        skrip + bobot YOLO (best.pt) + dataset_raw (isi sendiri)
  third_party/ffmpeg/bin/  ffprobe+ffmpeg (taruh manual, 211 MB/file)
  PRO.cmd             dispatcher: gui|stats|scan|dup|doctor|migrate|db|build|build-qt
  scripts/            db-stats/query/shell, scan, duplicates, build-core,
                      build-qt, migrate, install-startup, doctor (.ps1)
  data/               JSON user (behavior, doc_index, jobs, settings, activity)
                      + aiorganizer.db (cache mesin internal)
  results/            output engine (laporan CSV, hash cache)
  docs/               dokumentasi (PANDUAN_PEMULA mulai di sini)
  tests/              GoogleTest
```

Butuh Qt 6.8.x MSVC2022 di `D:\Qt\6.8.3\msvc2022_64` (atau set `QT_PREFIX`).
ffmpeg/ffprobe taruh manual di `third_party/ffmpeg/bin/`.

Pemula mulai dari `docs/PANDUAN_PEMULA.md` (5 menit).

## Pakai

```powershell
PRO.cmd gui                 # buka aplikasi desktop Qt
PRO.cmd build-qt            # rebuild aplikasi Qt
PRO.cmd doctor              # cek kesehatan (python/db/exe/ffmpeg/icon/Qt)
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
