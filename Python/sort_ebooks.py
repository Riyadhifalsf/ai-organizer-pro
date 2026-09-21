import os
import re
import shutil
from collections import Counter

SRC = r"D:\Gallery\PICTURES"
DST = r"D:\Gallery\EBOOKS"

RULES = [
    ("Japanese", r"jepang|japanese|jlpt|kanji|minna|52m"),
    ("Novel-Nonfiksi", r"tere liye|stieg larsson|paulo coelho|soji shimada|sherlock|sang alkemis|\bbintang\b|carl sagan|cosmos|sapiens|homo deus|demon.haunted|think and grow|psychology book|how psychology|filosofi teras|berdamai|kitab.merah|catatanhitam|akar dan dalang|sejarah dunia|sejarah yang tersembunyi|paris"),
    ("Bahasa-Ujian", r"cpns|sbmptn|simak|lolos|toefl|\btpa\b|wangsit|vocab|kosakata|kamus|kbbi|mandarin|\barab\b|soal|tes potensi|tpa"),
    ("Agama", r"syariah|islam\b|alqur"),
    ("Sekolah-Kuliah", r"\bkelas\b|sma|kurikulum|pdfdrive|fisika|kimia|matematik|biolog|sejarah|ekonomi|akuntansi|manajemen|statistik|kalkulus|integral|filsafat|psikologi|geografi|\bpeta\b|prosiding|praktikum|agribisnis|drainase|bimbingan|termodinamika|\bheat\b|engineering|biokimia|harper|tabel periodik|sifat fisik|pulp|kertas|longsoran|ketahanan|kerentanan|mitigasi|pangan|pengantar|teori|sistem informasi|pendidikan|strategi jitu|taman|tred|temananakkampus|schooling|mind\b|power\b|dion yulianto|grow rich|napolleon|monograf|tata|organisasi|perbankan|transportasi|perubahan|konseling|psikopatologi|musik|anak dan remaja|tanah|pangan|alo |gorontalo|mikrohidro|kontekstual|pembangkit|eter|panas|nap nap"),
]

c = Counter()
errs = []
for f in sorted(os.listdir(SRC)):
    src = os.path.join(SRC, f)
    if not os.path.isfile(src):
        continue
    if os.path.splitext(f.lower())[1] not in (".pdf", ".xz", ".zip", ".rar", ".epub"):
        continue
    fl = f.lower()
    bucket = "Lainnya"
    for name, pat in RULES:
        if re.search(pat, fl):
            bucket = name
            break
    dst = os.path.join(DST, bucket, f)
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            c["collide"] += 1
            errs.append("EXISTS: " + f)
            continue
        shutil.move(src, dst)
        c[bucket] += 1
    except Exception as e:
        c["error"] += 1
        errs.append(f"{f}: {e}")

print(dict(c))
for e in errs[:20]:
    print(e)
