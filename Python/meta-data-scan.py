import os
import json
from collections import defaultdict
import exifread
import cv2

# ================= CONFIG =================
SOURCE_DIR = r"D:\ImageCollection\scan"
OUTPUT_JSON = r"D:\ImageCollection\metadata_grouped.json"

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
VIDEO_EXT = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m2ts", ".mts")

# ==========================================

grouped = defaultdict(list)

# ===== IMAGE METADATA =====
def extract_image_metadata(path):
    data = {
        "file": path,
        "type": "image"
    }

    try:
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

        make = str(tags.get("Image Make", "Unknown"))
        model = str(tags.get("Image Model", "Unknown"))

        data["camera"] = f"{make} {model}".strip()

        if make == "Unknown" and model == "Unknown":
            group_key = "UNKNOWN_IMAGE"
        else:
            group_key = f"{make} {model}"

    except:
        group_key = "BROKEN_IMAGE"

    return group_key, data


# ===== VIDEO METADATA =====
def extract_video_metadata(path):
    data = {
        "file": path,
        "type": "video"
    }

    try:
        cap = cv2.VideoCapture(path)

        if not cap.isOpened():
            return "BROKEN_VIDEO", data

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cap.release()

        data["resolution"] = f"{width}x{height}"
        group_key = f"VIDEO_{width}x{height}"

    except:
        group_key = "BROKEN_VIDEO"

    return group_key, data


# ===== MAIN =====
def scan_and_group():
    for root, _, files in os.walk(SOURCE_DIR):
        for file in files:
            path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()

            if ext in IMAGE_EXT:
                key, meta = extract_image_metadata(path)
                grouped[key].append(meta)

            elif ext in VIDEO_EXT:
                key, meta = extract_video_metadata(path)
                grouped[key].append(meta)

    # ===== SUMMARY =====
    summary = {key: len(value) for key, value in grouped.items()}

    # ===== SAVE =====
    output = {
        "summary": summary,
        "data": grouped
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    # ===== PRINT RINGKASAN =====
    print("\n===== HASIL KELOMPOK =====")
    for k, v in sorted(summary.items(), key=lambda x: x[1], reverse=True):
        print(f"{k} -> {v} file")

    print(f"\n✅ Disimpan di: {OUTPUT_JSON}")


if __name__ == "__main__":
    scan_and_group()