import os
import shutil

S = r"D:\Gallery\PICTURES\Screenshots"
moved = renamed = 0
for dp, dn, fn in os.walk(S, topdown=False):
    if os.path.normpath(dp) == os.path.normpath(S):
        continue
    for f in fn:
        src = os.path.join(dp, f)
        dst = os.path.join(S, f)
        if os.path.exists(dst):
            base, ext = os.path.splitext(f)
            i = 2
            while os.path.exists(os.path.join(S, f"{base}_{i}{ext}")):
                i += 1
            dst = os.path.join(S, f"{base}_{i}{ext}")
            renamed += 1
        shutil.move(src, dst)
        moved += 1
    if not os.listdir(dp):
        os.rmdir(dp)

left = [d for d in os.listdir(S) if os.path.isdir(os.path.join(S, d))]
n = len([f for f in os.listdir(S) if os.path.isfile(os.path.join(S, f))])
print(f"moved={moved} renamed-dup={renamed} root-files={n} subdirs-left={left}")
