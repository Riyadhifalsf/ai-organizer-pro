import struct
import io
import zlib
import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image

P = (r"D:\Gallery\PICTURES\RAW\LIVP_TO_JPG"
     r"\UNKNOWN_2023_08_12_175831.livp")
OUT = (r"D:\Gallery\PICTURES\RAW\LIVP_TO_JPG"
       r"\UNKNOWN_2023_08_12_175831_uncat.jpg")
data = open(P, "rb").read()
pos = 0
found = {}
while True:
    i = data.find(b"PK\x03\x04", pos)
    if i < 0:
        break
    (ver, flag, method, mt, md, crc, cs, us,
     fnl, efl) = struct.unpack("<HHHHHIIIHH", data[i + 4:i + 30])
    fn = data[i + 30:i + 30 + fnl].decode("utf-8", "replace")
    start = i + 30 + fnl + efl
    found[fn] = (method, data[start:start + cs])
    pos = start + cs

print({k: (m, len(v)) for k, (m, v) in found.items()})
heic = next(v for k, v in found.items()
            if k.lower().endswith((".heic", ".heif")))
method, blob = heic
raw = zlib.decompress(blob, -15) if method == 8 else blob
img = Image.open(io.BytesIO(raw))
print(img.size, img.mode)
img.convert("RGB").save(OUT, quality=92)
print("saved", OUT)
