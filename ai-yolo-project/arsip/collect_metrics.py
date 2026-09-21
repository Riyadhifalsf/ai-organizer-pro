# collect_metrics.py — rangkum semua runs/classify/train*/results.csv jadi satu tabel.
# Pakai untuk memilih model secara objektif (bukan hardcode train12/train15).
import csv
from config import RUNS_DIR, REPORT_DIR

rows = []
for results_csv in sorted((RUNS_DIR / "classify").glob("train*/results.csv")):
    run = results_csv.parent.name
    try:
        with open(results_csv, newline="") as f:
            data = list(csv.DictReader(f))
        if not data:
            continue
        last = data[-1]
        best_acc = max(float(r.get("metrics/accuracy_top1", 0) or 0) for r in data)
        rows.append({
            "run": run,
            "epochs_done": len(data),
            "final_train_loss": last.get("train/loss", "?"),
            "final_val_loss": last.get("val/loss", "?"),
            "final_top1": last.get("metrics/accuracy_top1", "?"),
            "best_top1": round(best_acc, 4),
        })
    except Exception as e:
        print(f"SKIP {run}: {e}")

rows.sort(key=lambda r: r["best_top1"] if isinstance(r["best_top1"], float) else -1,
          reverse=True)
out = REPORT_DIR / "all_runs.csv"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["run", "epochs_done", "final_train_loss",
                                      "final_val_loss", "final_top1", "best_top1"])
    w.writeheader()
    w.writerows(rows)

for r in rows:
    print(f"{r['run']}: best_top1={r['best_top1']} (epochs={r['epochs_done']})")
print(f"\nOK: {len(rows)} runs dirangkum di {out}")
print("Samakan BEST_MODEL di config.py dengan run terbaik di atas.")
