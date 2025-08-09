import os

def generate_titles(work_dir, config_path):
    print("\n📝 Generating titles...")
    clips_dir = os.path.join(work_dir, "clips")
    for file in os.listdir(clips_dir):
        if file.endswith("_final.mp4"):
            name = file.replace("_final.mp4", "")
            title_filename = os.path.join(clips_dir, f"{name}_title.txt")
            count = 1
            while os.path.exists(title_filename):
                title_filename = os.path.join(clips_dir, f"{name}_title_{count}.txt")
                count += 1

            with open(title_filename, "w", encoding="utf-8") as f:
                f.write(f"🔥 Epic Clip: {name.replace('_', ' ').title()} #viral #shorts")
