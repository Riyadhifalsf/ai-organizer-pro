import os
import sys

target = sys.argv[1]
print(f"=== {target} ===", flush=True)
try:
    items = sorted(os.listdir(target))
except Exception as e:
    print(" err", e)
    raise SystemExit
for d in items:
    p = os.path.join(target, d)
    if os.path.islink(p):
        print(f"  {d}: link", flush=True)
        continue
    if os.path.isfile(p):
        try:
            print(f"  {d}: file {os.path.getsize(p)/1e6:.1f} MB", flush=True)
        except Exception:
            pass
        continue
    n = sz = 0
    try:
        for dp, dn, fn in os.walk(p):
            for f in fn:
                n += 1
                try:
                    sz += os.path.getsize(os.path.join(dp, f))
                except Exception:
                    pass
    except Exception:
        pass
    print(f"  {d}: {n} files, {sz/1e9:.1f} GB", flush=True)
print("scan done", flush=True)
