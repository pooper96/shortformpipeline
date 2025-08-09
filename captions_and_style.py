import os

def style_clips(work_dir, config_path):
    print("\n💬 Styling clips...")
    clips_dir = os.path.join(work_dir, "clips")
    for file in os.listdir(clips_dir):
        if file.endswith(".mp4") and not file.endswith("_final.mp4"):
            src = os.path.join(clips_dir, file)
            base_name = file.replace(".mp4", "_final.mp4")
            dst = os.path.join(clips_dir, base_name)
            count = 1
            while os.path.exists(dst):
                base_name = file.replace(".mp4", f"_final_{count}.mp4")
                dst = os.path.join(clips_dir, base_name)
                count += 1
            os.rename(src, dst)
