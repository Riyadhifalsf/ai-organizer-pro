# Aplikasi Qt AIOrganizerPro (0.4.0)

Pengganti web stack (HTML/Tauri/Node) yang diarsipkan ke
`_archive/web-legacy-20260922/`. Python tersisa HANYA untuk AI.

## Arsitektur (sesuai pohon)

```
AIOrganizerPro.exe (Qt 6 Widgets)
├── Qt 6: MainWindow + tab (Beranda/Video/Foto/Duplikat/Organizer/AI+Training/Jobs/DB/Aktivitas)
│         + sidebar + folder tree + dialog + context action + gallery
├── C++ Core: aiorganizer.exe via QProcess --json (scan/duplikat/hash/rename/move/jobs/proposal/audit/doctor/stats)
├── SQLite: dipakai core (skema v4); anotasi di data/video-annotations.json
├── FFmpeg: ffprobe/ffmpeg via QProcess (metadata, probe, broken detection)
└── Python: sidecar.py persisten (AI analyze/organize/yolo-classify + training); train.py tak diubah
```

## Tab dan fitur

- **Semua Video**: scan+index, galeri, player internal (mp4/webm; mkv/avi/dll
  langsung diarahkan ke Player Windows), buka/lokasi/rename/pindah/karantina,
  tag, catatan, cek duplikat exact.
- **Semua Foto**: galeri thumbnail lazy, viewer zoom/fit, aksi penuh
  (rename/pindah/karantina/tag/catatan), klasifikasi YOLO per foto.
- **Duplikat**: grup SHA-256, simpan+karantina terverifikasi, proposal.
- **Organizer**: video/foto by metadata, dry-run default, copy/rename/junk/prune.
- **AI + Training**: broken/size/analyze/yolo-classify + kartu training YOLO
  (status, dataset per kelas, epoch/batch/model/imgsz/patience, start/stop,
  polling log). Training detached + pid file; butuh dataset_raw terisi.
- **Jobs/Database/Aktivitas**: antrean worker, stats, doctor, saklar DB, log.

## Build

```powershell
PRO.cmd build-qt        # butuh Qt 6.8.3 MSVC2022 (D:\Qt\... atau QT_PREFIX)
```

Qt diinstall via `pip install aqtinstall` +
`aqt install-qt windows desktop 6.8.3 win64_msvc2022_64 -m qtmultimedia qtimageformats -O D:\Qt`.
`qt/build/` (hasil + DLL windeployqt) di-gitignore.
