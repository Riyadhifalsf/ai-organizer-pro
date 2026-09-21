import os

def scan(root, label):
    print(f"=== {label} ===", flush=True)
    try:
        items = sorted(os.listdir(root))
    except Exception as e:
        print(" err", e)
        return
    agg = {}
    for d in items:
        p = os.path.join(root, d)
        if os.path.islink(p):
            agg[d] = ("link", 0, 0)
            continue
        if os.path.isfile(p):
            try:
                agg[d] = ("file", 1, os.path.getsize(p))
            except Exception:
                agg[d] = ("file", 0, 0)
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
        agg[d] = ("dir", n, sz)
        print(f"  {d}: {n} files, {sz/1e9:.1f} GB", flush=True)
    print("scan done", flush=True)

scan(r"D:\\", "D:")
