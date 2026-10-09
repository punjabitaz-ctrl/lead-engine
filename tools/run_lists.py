"""Run the lead engine over every data/candidates/*.csv list and copy the filled workbooks and CSVs into lists/.
Usage: python3 tools/run_lists.py   (needs lead-engine-template.xlsx in the repo root)"""
import glob, os, shutil, subprocess, sys, tempfile

STAMP = "2026-10-09"
INDUSTRY = {"pt": "Physical therapy practice", "dentist": "Dental practice", "mental_health": "Mental health practice"}
os.makedirs("lists", exist_ok=True)
for seg in ("cardiology", "ophthalmology", "pt", "dentist", "mental_health"):
    for kind in ("practices", "individuals"):
        src = f"data/candidates/{seg}_{kind}.csv"
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, "-m", "leadengine", "run", "--source", "manual", "--manual", src, "--industry", INDUSTRY.get(seg, "Medical practice"),
                            "--target", "500", "--fresh", "--no-prompt", "--group-by-specialty", "--out", tmp],
                           check=True, stdin=subprocess.DEVNULL, capture_output=True, text=True)
            for ext in ("xlsx", "csv"):
                shutil.copy(sorted(glob.glob(f"{tmp}/*.{ext}"))[-1], f"lists/NJ_{seg}_{kind}_{STAMP}.{ext}")
        print("built", seg, kind)
