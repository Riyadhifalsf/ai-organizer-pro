import os
import subprocess
import json
import shutil

folder_path = r"D:\output\Videos\UNKNOWN"

video_extensions = (".mp4", ".mov", ".mkv", ".avi", ".m2ts", ".mts", ".ts")

def get_metadata(file):
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        file
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    
    tags = data.get("format", {}).get("tags", {})
    return tags

for filename in os.listdir(folder_path):
    if filename.lower().endswith(video_extensions):
        
        old_file = os.path.join(folder_path, filename)
        tags = get_metadata(old_file)
        
        # Ambil brand / device
        brand = tags.get("make") or tags.get("com.apple.quicktime.make")
        model = tags.get("model") or tags.get("com.apple.quicktime.model")
        
        if brand:
            folder_name = brand
        elif model:
            folder_name = model
        else:
            folder_name = "Unknown"
        
        target_folder = os.path.join(folder_path, folder_name)
        os.makedirs(target_folder, exist_ok=True)
        
        new_file = os.path.join(target_folder, filename)
        
        shutil.move(old_file, new_file)
        
        print(f"{filename} -> {folder_name}/")

print("Selesai!")