"""Pack precomputed runs over Pulang Pisau into space/data for the Hugging Face Space.

Three views of the same 14 km x 14 km area: the scripts on Sentinel-2 (29 Aug vs 21 Oct 2026), the scripts on
Landsat 8/9 (25 Aug vs 4 Oct 2026), and the Deep Agents runner answering the question in plain words.

Usage: uv run python space/build.py
"""

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = {
    "sentinel-2": ("Sentinel-2, 21 Oct 2026", REPO / "runs" / "kalteng-2"),
    "landsat": ("Landsat 8, 4 Oct 2026", REPO / "runs" / "kalteng-2-landsat"),
    "agent": ("Deep Agent, gpt-6-luna", REPO / "runs" / "agent-pulangpisau-2"),
}
PICTURES = ["pre/true_color.png", "pre/swir_false_color.png", "post/true_color.png", "post/swir_false_color.png"]


def main():
    data = REPO / "space" / "data"
    shutil.rmtree(data, ignore_errors=True)
    index = []
    for run_id, (title, run) in RUNS.items():
        dest = data / run_id
        dest.mkdir(parents=True)
        for pic in [*PICTURES, "compare/dnbr.png"]:
            if (run / pic).exists():
                shutil.copy(run / pic, dest / pic.replace("/", "-"))
        summary = json.loads((run / "compare" / "summary.json").read_text())
        pre = json.loads((run / "pre" / "scene.json").read_text())
        post = json.loads((run / "post" / "scene.json").read_text())
        entry = {
            "id": run_id,
            "title": title,
            "source": post.get("source", "sentinel-2"),
            "pre": {"id": pre["id"], "date": pre["date"]},
            "post": {"id": post["id"], "date": post["date"], "aoi_unusable_pct": post["aoi_unusable_pct"]},
            "confident_ha": summary["confident_burned_hectares"],
            "possible_ha": summary["possible_burned_hectares"],
            "compared_pct": summary["compared_pct"],
            "aoi_ha": summary["aoi_hectares"],
            "hotspot_check": summary.get("hotspot_check"),
            # open-ended class bounds are +-Infinity, which JSON (and JSON.parse) cannot hold
            "classes": [
                {**c, "dnbr_range": [None if abs(v) == float("inf") else v for v in c["dnbr_range"]]}
                for c in summary["classes"]
            ],
        }
        if (run / "answer.md").exists():
            entry["answer"] = (run / "answer.md").read_text()
            entry["run"] = json.loads((run / "run.json").read_text())
        index.append(entry)
    (data / "index.json").write_text(json.dumps(index, indent=2, allow_nan=False))
    print(f"packed {len(index)} runs into {data}")


if __name__ == "__main__":
    main()
