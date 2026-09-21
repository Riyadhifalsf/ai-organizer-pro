import os
import shutil

SRC = r"D:\Gallery\PICTURES\Uncategorized\Download"
DJ = r"D:\Documents\Japanese"
DR = r"D:\Documents"

PERSONAL = {
    "cv-riyadhifalsf.pdf",
    "rencana_anggaran_biaya_pekerjaan.docx",
    "backup-codes-riyadhifalsf.dev.txt",
    "headband pkkmb 2026[salinan].pdf",
    "41100-163844-1-pb.pdf",
    "kosakaa keterangan.pdf",
}

os.makedirs(DJ, exist_ok=True)
c_jp = c_pr = c_skip = 0
for dp, dn, fn in os.walk(SRC):
    for f in fn:
        if os.path.splitext(f.lower())[1] not in (".pdf", ".txt", ".docx"):
            continue
        src = os.path.join(dp, f)
        if f.lower() in PERSONAL:
            dst = os.path.join(DR, f)
            tag = "personal"
        else:
            dst = os.path.join(DJ, f)
            tag = "japanese"
        if os.path.exists(dst):
            print("EXISTS:", f)
            c_skip += 1
            continue
        shutil.move(src, dst)
        if tag == "personal":
            c_pr += 1
        else:
            c_jp += 1
print(f"japanese={c_jp} personal={c_pr} skipped={c_skip}")
