"""
Prepare IN-CXR (NIRT) into data/indian/manifest.csv

IN-CXR is distributed as normal vs abnormal images. This script scans whatever
folder you downloaded it into, figures out which images are normal vs abnormal
(from folder names), copies a balanced working set into data/indian/, and writes
manifest.csv.

USAGE:
    python -m src.prepare_incxr /path/to/your/IN-CXR/download

It looks for two subfolders whose names contain "normal" and "abnormal"
(case-insensitive). If your download is structured differently, pass explicit
folders:
    python -m src.prepare_incxr --normal /path/normal --abnormal /path/abnormal

It copies up to (CASES_PER_CLASS * SAFETY) of each class so you have headroom to
scale CASES_PER_CLASS later without re-running downloads.
"""

import sys
import shutil
import argparse
import csv
from pathlib import Path
from .config import DATA_INDIAN, CASES_PER_CLASS

SAFETY = 5  # copy 5x what we need now, for headroom
IMG_EXT = {".png", ".jpg", ".jpeg"}


def _find_class_folders(root: Path):
    normal = abnormal = None
    for p in root.rglob("*"):
        if p.is_dir():
            n = p.name.lower()
            if "abnormal" in n and abnormal is None:
                abnormal = p
            elif "normal" in n and "abnormal" not in n and normal is None:
                normal = p
    return normal, abnormal


def _images(folder: Path):
    return [p for p in folder.rglob("*") if p.suffix.lower() in IMG_EXT]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", help="IN-CXR download root folder")
    ap.add_argument("--normal", help="explicit normal-images folder")
    ap.add_argument("--abnormal", help="explicit abnormal-images folder")
    args = ap.parse_args()

    if args.normal and args.abnormal:
        normal_dir, abnormal_dir = Path(args.normal), Path(args.abnormal)
    elif args.root:
        normal_dir, abnormal_dir = _find_class_folders(Path(args.root))
    else:
        print("Provide the IN-CXR download folder, or --normal and --abnormal folders.")
        sys.exit(1)

    if not normal_dir or not abnormal_dir:
        print("Could not locate normal/abnormal subfolders. Pass them explicitly with "
              "--normal and --abnormal.")
        sys.exit(1)

    want = CASES_PER_CLASS * SAFETY
    DATA_INDIAN.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, folder in (("normal", normal_dir), ("abnormal", abnormal_dir)):
        imgs = _images(folder)[:want]
        print(f"  {label}: found {len(_images(folder))}, copying {len(imgs)}")
        for i, src in enumerate(imgs):
            dst_name = f"in_{label}_{i:04d}{src.suffix.lower()}"
            shutil.copy(src, DATA_INDIAN / dst_name)
            rows.append({"filename": dst_name, "label": label})

    with open(DATA_INDIAN / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["filename", "label"])
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {DATA_INDIAN/'manifest.csv'} ({len(rows)} images)")


if __name__ == "__main__":
    main()
