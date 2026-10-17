"""
STEP 1 of option B: generate radiologist-style reports.

For every enabled model, generate a report for each image in a balanced sample
of BOTH the Indian (IN-CXR) and Western (CheXpert) datasets. Save everything —
including the hidden truth of which dataset/model each report came from — to a
single JSON in results/. The blinding happens in the NEXT step.

USAGE:  python -m src.generate_reports
"""

import os
import sys
import json
import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .config import MODELS, DATA_INDIAN, DATA_CHEXPERT, RESULTS, CASES_PER_CLASS
from .dataset import load_dataset
from .clients import make_client

REQUIRED_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GEMINI_API_KEY"}


def _active():
    out = {}
    for name, cfg in MODELS.items():
        if not cfg["enabled"] or cfg["provider"] == "manual":
            continue
        ev = REQUIRED_ENV.get(cfg["provider"])
        if ev and os.environ.get(ev):
            out[name] = cfg
        else:
            print(f"  - {cfg['label']}: SKIPPED (no {ev})")
    return out


def main():
    print("GENERATING RADIOLOGIST-STYLE REPORTS (Indian + Western)")
    active = _active()
    if not active:
        print("No models active. Add keys to .env.")
        sys.exit(1)

    indian = load_dataset(DATA_INDIAN)
    western = load_dataset(DATA_CHEXPERT)
    print(f"  Indian: {len(indian)}   Western: {len(western)}")

    datasets = [("indian", indian), ("western", western)]
    records = []  # each: {report_id, dataset, model, case_id, truth, report}
    rid = 0
    for name, cfg in active.items():
        client = make_client(cfg["provider"], cfg["model_id"])
        print(f"\n{cfg['label']} [{cfg['model_id']}]")
        for ds_name, cases in datasets:
            print(f"  {ds_name}...")
            for i, case in enumerate(cases, 1):
                try:
                    rep = client.generate_report(case["image_bytes"], case["media_type"])
                except Exception as e:  # noqa: BLE001
                    print(f"    {ds_name} {i}/{len(cases)} FAILED: {e}")
                    rep = {"findings": "", "impression": "", "normal_or_abnormal": "error"}
                records.append({
                    "report_id": f"R{rid:05d}",
                    "dataset": ds_name,          # HIDDEN from radiologist
                    "model": name,               # HIDDEN from radiologist
                    "model_label": cfg["label"],
                    "model_id": cfg["model_id"],
                    "case_id": case["case_id"],
                    "truth_label": case["truth"],  # normal/abnormal ground truth
                    "report": rep,
                })
                rid += 1
                if i % 10 == 0:
                    print(f"    {i}/{len(cases)} done")

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    out = RESULTS / f"reports_{stamp}.json"
    out.write_text(json.dumps({
        "generated": stamp,
        "cases_per_class": CASES_PER_CLASS,
        "n_reports": len(records),
        "records": records,
    }, indent=2))
    print(f"\nWrote {len(records)} reports to {out}")
    print("Next: python -m src.build_grading_packet " + str(out.name))


if __name__ == "__main__":
    main()
