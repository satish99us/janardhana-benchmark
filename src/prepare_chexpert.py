"""
Prepare CheXpert into data/chexpert/manifest.csv (normal vs abnormal).

CheXpert ships with a CSV (train.csv / valid.csv) where each row is an image path
plus 14 finding columns valued 1.0 / 0.0 / -1.0 / blank. We collapse to:
  - "normal"   if "No Finding" == 1.0  (or all findings absent)
  - "abnormal" if any finding == 1.0

Then copy a balanced working set into data/chexpert/ and write manifest.csv.

USAGE:
    python -m src.prepare_chexpert /path/to/CheXpert-v1.0-small

Expects the CheXpert folder containing the label CSV (train.csv or valid.csv)
and the image folders referenced by it.
"""

import sys
import csv
import shutil
import argparse
from pathlib import Path
from .config import DATA_CHEXPERT, CASES_PER_CLASS

SAFETY = 5
FINDING_COLS = [
    "Enlarged Cardiomediastinum", "Cardiomegaly", "Lung Opacity", "Lung Lesion",
    "Edema", "Consolidation", "Pneumonia", "Atelectasis", "Pneumothorax",
    "Pleural Effusion", "Pleural Other", "Fracture", "Support Devices",
]


def _label_for_row(row: dict) -> str:
    # Normal if "No Finding" positive
    if row.get("No Finding", "").strip() in ("1", "1.0"):
        return "normal"
    # Abnormal if any finding positive
    for col in FINDING_COLS:
        if row.get(col, "").strip() in ("1", "1.0"):
            return "abnormal"
    # Otherwise (all absent / uncertain / blank) treat as normal
    return "normal"


def _find_csv(root: Path):
    for name in ("train.csv", "valid.csv", "train_visualCheXbert.csv"):
        hits = list(root.rglob(name))
        if hits:
            return hits[0]
    csvs = list(root.rglob("*.csv"))
    return csvs[0] if csvs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="CheXpert download root (contains label csv + images)")
    args = ap.parse_args()
    root = Path(args.root)

    label_csv = _find_csv(root)
    if not label_csv:
        print(f"No label CSV found under {root}. Expected train.csv or valid.csv.")
        sys.exit(1)
    print(f"  using labels: {label_csv}")

    want = CASES_PER_CLASS * SAFETY
    buckets = {"normal": [], "abnormal": []}
    with open(label_csv, newline="") as f:
        for row in csv.DictReader(f):
            path_field = row.get("Path") or row.get("path") or ""
            # CheXpert paths look like "CheXpert-v1.0-small/train/patient.../view1_frontal.jpg"
            # keep frontal only for a clean comparison
            if "frontal" not in path_field.lower():
                continue
            lbl = _label_for_row(row)
            if len(buckets[lbl]) < want:
                buckets[lbl].append(path_field)
        # (we stop collecting once both buckets are full enough)

    DATA_CHEXPERT.mkdir(parents=True, exist_ok=True)
    rows = []
    for lbl in ("normal", "abnormal"):
        print(f"  {lbl}: collected {len(buckets[lbl])}")
        for i, rel in enumerate(buckets[lbl]):
            # resolve image path relative to the dataset root (handle the
            # leading "CheXpert-v1.0-small/" prefix gracefully)
            candidates = [root / rel, root / Path(*Path(rel).parts[1:])]
            src = next((c for c in candidates if c.exists()), None)
            if not src:
                continue
            dst_name = f"cx_{lbl}_{i:04d}{src.suffix.lower()}"
            shutil.copy(src, DATA_CHEXPERT / dst_name)
            rows.append({"filename": dst_name, "label": lbl})

    with open(DATA_CHEXPERT / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["filename", "label"])
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {DATA_CHEXPERT/'manifest.csv'} ({len(rows)} images)")


if __name__ == "__main__":
    main()
