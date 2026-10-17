"""
Dataset loading with BALANCED sampling.

Both datasets are read from a CSV manifest the prep scripts build:

    filename,label
    img001.png,normal
    img002.png,abnormal

Balanced sampling (CASES_PER_CLASS each of normal/abnormal) is enforced here so
an imbalanced source (IN-CXR is ~93% normal) can't produce a misleading result.
"""

import csv
import random
from pathlib import Path
from .config import CASES_PER_CLASS, TASK_LABELS

random.seed(42)  # reproducible sampling


def _media_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    raise ValueError(f"Unsupported image type: {path.name} (use jpg/jpeg/png)")


def load_dataset(folder: Path, per_class: int = CASES_PER_CLASS):
    """
    Reads manifest.csv, takes a balanced random sample of `per_class` normal and
    `per_class` abnormal, returns list of:
        {case_id, image_bytes, media_type, truth}  where truth in {normal, abnormal}
    """
    manifest = folder / "manifest.csv"
    if not manifest.exists():
        raise FileNotFoundError(
            f"No manifest.csv in {folder}. Run the prep script for this dataset "
            f"first (see README)."
        )

    buckets = {lbl: [] for lbl in TASK_LABELS}
    with open(manifest, newline="") as f:
        for row in csv.DictReader(f):
            lbl = (row.get("label") or "").strip().lower()
            if lbl in buckets:
                buckets[lbl].append(row["filename"])

    for lbl in TASK_LABELS:
        if len(buckets[lbl]) < per_class:
            raise ValueError(
                f"{folder.name}: only {len(buckets[lbl])} '{lbl}' images, "
                f"need {per_class}. Lower CASES_PER_CLASS in config.py or add data."
            )
        random.shuffle(buckets[lbl])

    out = []
    for lbl in TASK_LABELS:
        for fname in buckets[lbl][:per_class]:
            img_path = folder / fname
            if not img_path.exists():
                print(f"  ! skipping missing image: {img_path.name}")
                continue
            out.append({
                "case_id": fname,
                "image_bytes": img_path.read_bytes(),
                "media_type": _media_type(img_path),
                "truth": lbl,
            })
    random.shuffle(out)  # mix normal/abnormal so order isn't a tell
    return out
