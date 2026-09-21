# Integrasi YOLO ↔ AIOrganizerPro (aman, non-destruktif)

`ai-yolo-project/` adalah **kanonis dan TIDAK diubah**: training (`train.py`),
inference (`run.py`), config (`config.py`), dataset, `runs/*/weights/best.pt`
tetap milik YOLO. Organizer hanya **memanggil** lewat jembatan.

## Cara kerja

```
organizer.py yolo-classify <folder> [--out DIR] [--limit N] [--dry-run] [--apply]
      └── app/ai/yolo_bridge.py ──lazy──▶ ai-yolo-project/config.py (MODEL, HIGH_TH…)
                                   ──lazy──▶ ultralytics.YOLO (opsional)
```

- `yolo_bridge.project_root()` = `<pro-root>/ai-yolo-project` (atau env `AIORG_YOLO_PROJECT`).
- `is_available()` = cek folder + `ultralytics` + file model. Gagal → pesan jelas, tanpa crash.
- `classify_images()` = prediksi saja, tanpa pindah file (mirip `run.py` mode single).
- `run()` = tulis `yolo_plan_<stamp>.csv` ke `results/reports/`, pindah HANYA bila `--apply`.

## Pakai

```powershell
# cek kesiapan (model + deps)
python organizer.py yolo-classify D:\foto --limit 5
# eksekusi pindah terverifikasi ke YOLO/<high|medium|low>/<kelas>/
python organizer.py yolo-classify D:\foto --apply
# copy saja (original tetap)
python organizer.py yolo-classify D:\foto --apply --apply-copy
# model kustom / threshold kustom
python organizer.py yolo-classify D:\foto --yolo-model D:\m.pt --yolo-conf 0.6 --out D:\out
```

Via sidecar (GUI/Node):

```json
{"id": 1, "cmd": "yolo-classify", "root": "D:\\foto", "limit": 50}
```

## Kontrak aman

1. Default **dry-run**: tidak ada file dipindah/dihapus.
2. `--apply` = pindah-terverifikasi (copy → bandingkan → hapus sumber). Gagal verifikasi → catat, lanjut.
3. YOLO `run.py` asli (yang MOVE file ke `results/sorted/`) **tidak dipakai** organizer;
   organizer punya alur sendiri ke `YOLO/<level>/<kelas>/`.
4. Dependensi `ultralytics` tetap opsional (stdlib-first organizer tidak dilanggar).

## Kembalikan bila rusak

Backup pre-merge: `_archive/pre-merge-20260922/` (`engine.py.bak`, `sidecar.py.bak`).
Hapus `app/ai/yolo_bridge.py` + revert 2 file itu → kembali seperti semula.
`ai-yolo-project/` tidak pernah disentuh merge ini.
