# AIOrganizerPro 0.4.0 — aplikasi desktop Qt6/C++

```
ai-organizer-pro\
  AIOrganizerPro.exe    APLIKASI desktop Qt6 — klik 2x langsung jalan
  qt/                 sumber GUI Qt (MainWindow, tab, player, viewer, gallery)
  src/                core C++ (scanner, hashing, duplicate detection, jobs)
  aiorganizer.exe     core C++ jadi (dipakai Qt via QProcess --json)
  app/                Python AI: ai/ (YOLO classify/training, analyze, organize,
                      broken, jobs, behavior) + core/ (engine) — dipanggil Qt
  organizer.py + sidecar.py  launcher & jembatan JSON di root
  app/ai/yolo/        skrip + bobot YOLO (best.pt) + dataset_raw (isi sendiri)
  bin/ffmpeg/           ffprobe+ffmpeg (taruh manual, 211 MB/file)
  PRO.cmd             dispatcher: gui|scan|dup|doctor|build|build-qt
  scripts/            scan, duplicates, build-core, build-qt, doctor (.ps1)
  data/               JSON user (behavior, doc_index, jobs, settings, activity)
                      + annotations (tanpa database persistent)
  results/            output engine (laporan CSV, hash cache)
  docs/               dokumentasi (PANDUAN_PEMULA mulai di sini)
  tests/              GoogleTest
```

Butuh Qt 6.8.x MSVC2022 untuk rebuild; `qt/build` dapat dikonfigurasi ulang dengan `QT_PREFIX`.
ffmpeg/ffprobe taruh manual di `bin/ffmpeg/`.

Pemula mulai dari `docs/PANDUAN_PEMULA.md` (5 menit).

## Workspace

Aplikasi sekarang memakai workspace desktop native: **Beranda**, **Video**, **Foto**, **Duplikat**, **Organizer**, **AI + Training**, **Jobs**, **Aktivitas**, **Pengaturan**, dan **Tentang**. Preview video memiliki timeline, maju/mundur 10 detik, volume, serta autoplay yang dapat diatur.

State pengguna disimpan sebagai JSON/log. **Tidak ada database persistent**; core yang membutuhkan SQLite memakai database sementara `:memory:`.

## Pakai

```powershell
PRO.cmd gui                 # buka aplikasi desktop Qt
PRO.cmd build-qt            # rebuild aplikasi Qt
PRO.cmd doctor              # cek kesehatan runtime
PRO.cmd scan D:\Data        # scan cepat (baca saja)
PRO.cmd dup D:\Data         # cari duplikat exact
PRO.cmd build               # rebuild core + ctest + refresh aiorganizer.exe
```

## Kontrak aman (dari CARA_PAKAI + AGENTS + MASTER doc)

Tidak pernah menghapus. Move hanya yg disetujui + verifikasi + rollback log.
Broken default copy. Dry-run tersedia. Registry hanya HKCU. AI hanya pengusul
(confidence<0.3 = tanpa saran rename), engine deterministik yang mengeksekusi.
Detail: `docs\`.
