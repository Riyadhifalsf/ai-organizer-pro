# Panduan Pemula (5 menit)

AIOrganizerPro 100% offline. Tidak ada akun, tidak ada internet, tidak ada
yang terhapus permanen.

## 1. Buka aplikasi

`PRO.cmd gui` — atau klik `qt\build\AIOrganizerPro.exe`.

Sapaan pertama menjelaskan 3 langkah. Folder library-mu tersimpan otomatis
di `data/settings.json` (boleh dibuka & diubah manual):

```json
{
  "library_root": "D:\\Foto",
  "dry_run_default": true,
  "llm_enabled": false,
  "first_run": false
}
```

## 2. Scan pertama (baca saja, aman)

1. Isi folder library di kiri atas.
2. Tab **Semua Video/Foto** → **Scan & Index**.
3. Klik file untuk preview + metadata. Semua tombol aksi pindah selalu
   pratinjau dulu (dry-run).

## 3. Memahami file JSON milikmu

| File | Isi (bisa dibuka Notepad) |
|---|---|
| `data/behavior.jsonl` | 1 baris = 1 kebiasaanmu (folder dibuka, scan, karantina). Dari sini AI memberi saran. |
| `data/behavior_prefs.json` | Pilihanmu (mis. auto per folder). |
| `data/doc_index.json` | Hasil AI baca dokumen: kategori, confidence, saran nama. |
| `data/jobs.json` | Antrean kerja (pending/running/done). |
| `data/activity.log` | Jejak semua aksi (kapan, apa, ke mana). |
| `data/video-annotations.json` | Tag + catatan per file. |
| `data/aiorganizer.db` | Cache mesin (kecepatan index). Tidak perlu dibuka. |

## 4. Klasifikasi + training YOLO

- Tab **AI + Training** → mode `yolo-classify` untuk menebak isi foto.
- Kartu training: isi `ai-yolo-project\dataset_raw\<kelas>\*.jpg` dulu,
  atur epoch/batch, **Latih**. Berjalan background; **Stop** kapan saja.

## 5. Kalau ada yang aneh

`PRO.cmd doctor` — semua harus `[OK]`. File tidak pernah dihapus aplikasi:
yang dikarantina ada di folder `99_To-Delete`, bisa dipindah balik manual.
