# AIOrganizerPro Desktop GUI — Implementasi 2026-09-22

Perubahan ini membuat GUI Tauri menjadi panel desktop yang benar-benar terhubung ke backend native, bukan mock data.

## Fungsi video yang aktif

- Pilih video lewat native Windows OpenFileDialog.
- Muat video dari path dan baca metadata file.
- Buka video memakai aplikasi default Windows.
- Tampilkan lokasi file di Explorer.
- Player HTML5 untuk preview lokal saat WebView mengizinkannya.
- Probe metadata dengan `ffprobe`: codec, profile, resolusi, FPS, aspect ratio, durasi, audio codec.
- Cek duplikat exact dari file yang dipilih melalui SHA-256 core.
- Rename file dengan validasi nama dan ekstensi otomatis.
- Move file ke folder tujuan; tujuan dibuat otomatis bila belum ada.
- Move lintas drive memakai `copy -> verifikasi isi -> delete source` sehingga tidak memakai rename lintas-volume yang tidak aman.
- Quarantine ke `99_To-Delete` dengan nama unik; bukan delete permanen.
- Simpan tag dan catatan lokal per file.
- Tag/catatan ikut dimigrasikan saat file di-rename/move/quarantine.
- Semua operasi desktop dicatat ke activity log.

## Fungsi library

- Library root dipilih secara native dan disimpan di localStorage.
- Daftar video dibaca dari filesystem nyata melalui sidecar Python.
- Jumlah video, total file, non-media, dan ukuran video diambil dari data filesystem nyata.
- Search global dan filter library tidak menggunakan data contoh.
- Folder tree dan extension tree dibangun dari file yang benar-benar ditemukan.
- Scan & Index tetap menggunakan core C++ dan database aktif.

## Fungsi AI dan organizer

- `video-broken`
- `image-broken`
- `size`
- `analyze`
- `scan`
- `karantina`
- Organizer video/foto
- Seleksi file individual
- Plan/dry-run vs Apply
- Copy instead of move
- Rename by date
- Content rules
- Junk -> `99_To-Delete`
- Prune empty folders
- Export laporan organizer

## Duplicate dan proposal

Alur duplicate dibuat eksplisit:

1. Scan duplicate exact.
2. Pilih file canonical yang dipertahankan.
3. Pilih tujuan.
4. Untuk move: tampilkan konfirmasi lalu jalankan core verified move.
5. Untuk proposal: buat proposal tanpa memindahkan file.
6. Proposal dapat di-preview, approve, atau reject.

## Database, jobs, audit, activity

- Database ON/OFF tetap tersedia.
- `docs_list` menggunakan database aktif melalui `AIORG_DB`; tidak membaca database stale.
- Job queue dapat enqueue, claim, pause, resume, cancel, list, dan **run one job secara nyata** dari desktop.
- Worker desktop mendukung job `scan`, `duplicates`, `ai`, dan `organize`.
- Bila job gagal setelah di-claim, worker tetap memanggil `job_finish(..., failed, ...)` sehingga job tidak tertinggal dalam keadaan claimed.
- Activity log dapat dimuat, diekspor, dan dihapus tanpa menghapus database.
- Audit trail tetap read-only dari GUI.

## Runtime path fixes

Backend mencari resource dari lokasi executable/ancestor/resource bundle, bukan mengandalkan path relatif `../` yang berubah antara debug/release.

Python runtime dicari berurutan dari environment variable, bundled Python, `.venv`, lalu Python launcher/`python3`.

FFprobe dicari dari environment variable, bundle aplikasi, lalu PATH.

## Pengujian yang sudah dilakukan

- JavaScript syntax check: `node --check gui/app.js` — PASS.
- Python syntax check: `python -m py_compile engine-py/*.py` — PASS.
- HTML structural parse dengan stdlib `html.parser` — PASS.
- 33 button IDs GUI — seluruhnya memiliki handler.
- Semua command `invoke(...)` yang dipakai GUI memiliki handler Tauri command.
- Python sidecar smoke test (`ping`, `list-videos`) — PASS.
- Python engine dry-run scan pada folder uji — PASS.

Build Tauri/Rust penuh tidak dapat dikompilasi di lingkungan pengeditan ini karena toolchain `rustc/cargo` tidak tersedia. Source sudah dipersiapkan untuk dibangun dengan toolchain Tauri v2 yang sesuai.

## 2026-09-22 media/workspace pass
- Added persistent workspace tabs in the top bar (add/activate/close).
- Added real folder tree backed by filesystem traversal; no seeded folder data.
- Added real photo library with disk-backed scan, thumbnails, in-app image preview, zoom, metadata, and Windows external-open fallback.
- Switched internal video preview to Tauri asset protocol instead of direct `file://` URLs, allowing local media to be loaded by the WebView when the codec is supported.
- Added native photo file picker and generic file metadata command.
- Enabled Tauri global API + asset protocol configuration and media/image CSP entries.
- Kept destructive actions explicit and audited; unsupported codecs fall back to the Windows player rather than pretending the in-app player can decode them.
