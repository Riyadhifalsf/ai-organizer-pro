# Panduan Pemula (5 menit)

AIOrganizerPro 100% offline. Tidak ada akun, tidak ada internet, tidak ada
yang terhapus permanen.

## 1. Buka aplikasi

`PRO.cmd gui` — atau klik `AIOrganizerPro.exe` di folder utama.

Sapaan pertama menjelaskan 3 langkah. Folder library-mu tersimpan otomatis
di `data/settings.json` (boleh dibuka & diubah manual):

```json
{
  "library_root": "D:\\Foto",
  "autoplay_preview": true,
  "confirm_file_actions": true,
  "dry_run_default": true,
  "llm_enabled": false,
  "thumbnail_batch": 24,
  "first_run": false
}
```

## 2. Scan pertama (baca saja, aman)

1. Pilih Library Root di sidebar.
2. Buka **Video** atau **Foto** lalu muat/scan library.
3. Klik file untuk preview + metadata. Preview video punya timeline,
   mundur 10 detik, maju 10 detik, volume, dan autoplay yang bisa diatur.
4. Gunakan Organizer dalam mode dry-run sebelum menerapkan perpindahan.

## 3. Memahami file JSON milikmu

| File | Isi (bisa dibuka Notepad) |
|---|---|
| `data/behavior.jsonl` | 1 baris = 1 kebiasaanmu (folder dibuka, scan, karantina). Dari sini AI memberi saran. |
| `data/behavior_prefs.json` | Pilihanmu (mis. auto per folder). |
| `data/doc_index.json` | Hasil AI baca dokumen: kategori, confidence, saran nama. |
| `data/jobs.json` | Antrean kerja (pending/running/done). |
| `data/activity.log` | Jejak semua aksi (kapan, apa, ke mana). |
| `data/video-annotations.json` | Tag + catatan per file. |
| `data/` | State aplikasi berbentuk JSON/log; tidak ada `aiorganizer.db` persistent. |

## 4. Klasifikasi + training YOLO

- Tab **AI + Training** → mode `yolo-classify` untuk menebak isi foto.
- Kartu training: isi `app\ai\yolo\dataset_raw\<kelas>\*.jpg` dulu,
  atur epoch/batch, **Latih**. Berjalan background; **Stop** kapan saja.

## 5. Kalau ada yang aneh

`PRO.cmd doctor` — semua harus `[OK]`. File tidak pernah dihapus aplikasi:
yang dikarantina ada di folder `99_To-Delete`, bisa dipindah balik manual.
