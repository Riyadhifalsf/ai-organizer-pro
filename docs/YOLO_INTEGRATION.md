# Integrasi YOLO (blend 2026-09-22)

Model + skrip YOLO tinggal di `app/ai/yolo/` (dulu folder terpisah
`ai-yolo-project/`, kini dilebur; bukti akurasi di `docs/yolo-eval/`).

```
app/ai/yolo_bridge.py ──lazy──▶ app/ai/yolo/config.py (HIGH_TH/LOW_TH/…)
                        ──lazy──▶ ultralytics.YOLO (opsional)
                        ──utama─▶ app/ai/yolo/best.pt (bobot bawaan)
```

## Pakai

```powershell
python organizer.py cli yolo-classify D:\foto --limit 5   # dry-run
python organizer.py cli yolo-classify D:\foto --apply     # pindah terverifikasi
```

Tab **AI + Training** di aplikasi Qt: status, dataset per kelas
(`app/ai/yolo/dataset_raw/<kelas>/`), latih background + stop + log.
Override bobot: `--yolo-model D:\m.pt`.
