import os

root = r"D:\development\project-coding"
SKIP = {"node_modules", ".git", "build", ".gradle", ".gradle-user-home",
        ".dart_tool", ".idea", "__pycache__", ".vscode", "vendor",
        "packages", ".expo", "dist"}
EXTS = (".zip", ".rar", ".7z", ".tar.gz", ".tgz", ".tar.xz", ".tar")

out = []
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d not in SKIP and not d.startswith(".")]
    for f in fn:
        fl = f.lower()
        if fl.endswith(EXTS):
            p = os.path.join(dp, f)
            try:
                out.append((os.path.getsize(p), os.path.relpath(p, root)))
            except OSError:
                pass

out.sort(reverse=True)
print(len(out), "archives")
for s, p in out:
    print(f"{s/1e6:.1f} MB {p[:120]}")
