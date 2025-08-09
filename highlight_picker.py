import json
import os

def pick_highlights(transcript, work_dir, config_path):
    print("\n✨ Picking highlights...")
    highlights = []
    for i, seg in enumerate(transcript[:2]):
        highlights.append({"start": seg['start'], "end": seg['end']})
    with open(os.path.join(work_dir, "highlights.json"), "w") as f:
        json.dump(highlights, f, indent=2)
    return highlights
