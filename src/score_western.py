"""
AUTOMATED Western scoring: compare each model's generated report against the
CheXpert validation labels (radiologist-consensus, 14 findings).

This is the Western counterpart to the blinded radiologist grading used for the
Indian set. CheXpert ships structured ground truth, so no human is needed here:
we map our copied cx_*.jpg back to their original valid.csv rows (by content
hash), then score the model output two ways:

  1. normal/abnormal accuracy  (model 'normal_or_abnormal' vs CheXpert label)
  2. per-finding detection      (keyword scan of model free-text vs each label)

USAGE:  python -m src.score_western reports_<stamp>.json
"""

import re
import sys
import csv
import json
import hashlib
from pathlib import Path
from collections import defaultdict

from .config import RESULTS, DATA_CHEXPERT, ROOT

VALID_CSV = (ROOT / "downloads" / "chexpert" /
             "CheXpert-v1.0 batch 1 (validate & csv)" / "valid.csv")

# CheXpert label column -> regex of synonyms to look for in the model's free text
FINDING_PATTERNS = {
    "Cardiomegaly": r"cardiomegaly|enlarged heart|cardiac enlargement|increased cardiothoracic",
    "Edema": r"edema|oedema|pulmonary congestion|vascular congestion",
    "Consolidation": r"consolidation|airspace opacit",
    "Pneumonia": r"pneumonia|infective|infection",
    "Atelectasis": r"atelectasis|collapse|volume loss",
    "Pneumothorax": r"pneumothorax",
    "Pleural Effusion": r"effusion|blunting of the costophrenic|blunted costophrenic",
    "Lung Opacity": r"opacit|infiltrat|consolidation|mass|nodule",
    "Fracture": r"fracture",
    "Support Devices": r"tube|catheter|line|pacemaker|device|lead|wire|port",
}


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def load_chexpert_labels() -> dict[str, dict]:
    """hash(image bytes) -> label row dict from valid.csv.

    valid.csv Path looks like 'CheXpert-v1.0/valid/patientX/studyY/view1_frontal.jpg';
    on disk those live under VALID_CSV.parent / 'valid/...'. We resolve each row to
    its file and hash it so we can match our copied cx_*.jpg by content.
    """
    base = VALID_CSV.parent
    labels: dict[str, dict] = {}
    with open(VALID_CSV, newline="") as f:
        for row in csv.DictReader(f):
            rel = Path(row["Path"])
            # drop the leading 'CheXpert-v1.0' prefix, keep 'valid/patient.../...jpg'
            on_disk = base / Path(*rel.parts[1:])
            if on_disk.exists():
                labels[md5(on_disk)] = row
    return labels


def derive_truth(row: dict) -> str:
    if (row.get("No Finding", "") or "").strip() in ("1", "1.0"):
        return "normal"
    return "abnormal"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m src.score_western reports_<stamp>.json")
        sys.exit(1)
    reports_file = RESULTS / sys.argv[1]
    if not reports_file.exists():
        reports_file = Path(sys.argv[1])
    data = json.loads(reports_file.read_text())
    records = [r for r in data["records"] if r["dataset"] == "western"]

    print("Mapping CheXpert images to valid.csv labels (by content hash)...")
    labels = load_chexpert_labels()
    cx_hash = {p.name: md5(p) for p in DATA_CHEXPERT.glob("cx_*.jpg")}
    print(f"  valid.csv labels indexed: {len(labels)}   our cx images: {len(cx_hash)}")

    by_model = defaultdict(lambda: {"n": 0, "na_correct": 0, "matched": 0,
                                    "finding": defaultdict(lambda: defaultdict(int))})
    for r in records:
        h = cx_hash.get(r["case_id"])
        row = labels.get(h) if h else None
        m = by_model[r["model_label"]]
        m["n"] += 1
        if not row:
            continue
        m["matched"] += 1
        truth = derive_truth(row)
        pred = (r["report"].get("normal_or_abnormal") or "").lower()
        if pred == truth:
            m["na_correct"] += 1
        text = (r["report"].get("findings", "") + " " +
                r["report"].get("impression", "")).lower()
        for col, pat in FINDING_PATTERNS.items():
            label_pos = (row.get(col, "") or "").strip() in ("1", "1.0")
            pred_pos = bool(re.search(pat, text))
            cell = m["finding"][col]
            if label_pos and pred_pos:
                cell["tp"] += 1
            elif label_pos and not pred_pos:
                cell["fn"] += 1
            elif not label_pos and pred_pos:
                cell["fp"] += 1
            else:
                cell["tn"] += 1

    print("\n== WESTERN AUTOMATED SCORE (vs CheXpert valid labels) ==")
    for model, m in by_model.items():
        matched = m["matched"]
        acc = m["na_correct"] / matched if matched else 0
        print(f"\n{model}: matched {matched}/{m['n']}  "
              f"normal/abnormal acc = {acc:.1%}")
        for col, c in m["finding"].items():
            tp, fn, fp, tn = c["tp"], c["fn"], c["fp"], c["tn"]
            sens = tp / (tp + fn) if (tp + fn) else None
            spec = tn / (tn + fp) if (tn + fp) else None
            ss = f"{sens:.0%}" if sens is not None else "  -"
            sp = f"{spec:.0%}" if spec is not None else "  -"
            print(f"    {col:18s} sens={ss:>4s} spec={sp:>4s}  (tp{tp} fn{fn} fp{fp} tn{tn})")

    out = RESULTS / "western_auto_result.json"
    out.write_text(json.dumps(
        {m: {"matched": v["matched"], "n": v["n"], "na_correct": v["na_correct"],
             "finding": {k: dict(d) for k, d in v["finding"].items()}}
         for m, v in by_model.items()}, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
