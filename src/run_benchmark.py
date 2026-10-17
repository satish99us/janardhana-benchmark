"""
Janardhana Benchmark — main runner (normal-vs-abnormal task).

Loads the Indian (IN-CXR) and Western (CheXpert) datasets, runs every enabled
model on a BALANCED sample of both, scores normal-vs-abnormal, and writes the
India-vs-West accuracy delta to results/ as JSON + a readable summary.

RUN:  python -m src.run_benchmark
(or ask the Cursor agent to run this file)

Makes live, paid API calls with YOUR keys on YOUR machine. Starts small
(CASES_PER_CLASS=30 => 60 images/dataset). Scale up after first signal.
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
from .scoring import score_model_on_dataset, compute_delta

REQUIRED_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
}


def _active_models():
    active = {}
    for name, cfg in MODELS.items():
        if not cfg["enabled"]:
            continue
        if cfg["provider"] == "manual":
            print(f"  - {cfg['label']}: manual/no-API, skipped in automated run")
            continue
        env_var = REQUIRED_ENV.get(cfg["provider"])
        if not env_var or not os.environ.get(env_var):
            print(f"  - {cfg['label']}: SKIPPED (no {env_var} in .env)")
            continue
        active[name] = cfg
    return active


def _run(client, cases, label):
    preds, truths = [], []
    for i, case in enumerate(cases, 1):
        try:
            pred = client.classify(case["image_bytes"], case["media_type"])
        except Exception as e:  # noqa: BLE001
            print(f"      {label} {i}/{len(cases)} ({case['case_id']}): FAILED — {e}")
            pred = {"assessment": "invalid"}
        preds.append(pred)
        truths.append(case["truth"])
        if i % 10 == 0:
            print(f"      {label}: {i}/{len(cases)} done")
    return preds, truths


def main():
    print("=" * 70)
    print("JANARDHANA CHEST X-RAY BENCHMARK  —  normal vs abnormal")
    print("India (IN-CXR / NIRT)  vs  West (CheXpert / Stanford)")
    print("=" * 70)

    print("\nActive models:")
    active = _active_models()
    if not active:
        print("\nNo models active. Add keys to .env and enable models in config.py.")
        sys.exit(1)

    print("\nLoading datasets (balanced sample)...")
    try:
        indian = load_dataset(DATA_INDIAN)
        western = load_dataset(DATA_CHEXPERT)
    except (FileNotFoundError, ValueError) as e:
        print(f"\nDATASET ERROR: {e}")
        sys.exit(1)
    print(f"  Indian:  {len(indian)} cases (balanced)")
    print(f"  Western: {len(western)} cases (balanced)")

    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    report = {
        "run_date": stamp,
        "task": "normal_vs_abnormal",
        "cases_per_class": CASES_PER_CLASS,
        "indian_dataset": "IN-CXR (NIRT, National TB Prevalence Survey 2019-21)",
        "western_dataset": "CheXpert (Stanford)",
        "n_indian": len(indian),
        "n_western": len(western),
        "models": {},
    }

    for name, cfg in active.items():
        print(f"\n--- {cfg['label']}  [{cfg['model_id']}] ---")
        client = make_client(cfg["provider"], cfg["model_id"])
        print("  Indian (IN-CXR)...")
        ip, it = _run(client, indian, "indian")
        print("  Western (CheXpert)...")
        wp, wt = _run(client, western, "western")
        isc = score_model_on_dataset(ip, it)
        wsc = score_model_on_dataset(wp, wt)
        delta = compute_delta(isc, wsc)
        report["models"][name] = {
            "label": cfg["label"], "model_id": cfg["model_id"],
            "indian": isc, "western": wsc, "delta": delta,
        }
        ad = delta["accuracy_delta"]
        print(f"  >> accuracy  India: {isc['accuracy']}  West: {wsc['accuracy']}  "
              f"delta(W-I): {ad}")
        if ad is not None and ad > 0:
            print(f"  >> WORSE on Indian data by {round(ad*100,1)} points (supports thesis)")

    RESULTS.mkdir(exist_ok=True)
    safe = stamp.replace(":", "-")
    out_json = RESULTS / f"benchmark_{safe}.json"
    out_json.write_text(json.dumps(report, indent=2))
    summary = _summary(report)
    (RESULTS / f"summary_{safe}.txt").write_text(summary)

    print("\n" + "=" * 70)
    print(summary)
    print("=" * 70)
    print(f"\nFull JSON: {out_json}")
    print("\nPaste the JSON contents back to Claude for interpretation & next steps.")


def _summary(r: dict) -> str:
    L = []
    L.append(f"JANARDHANA BENCHMARK  —  {r['run_date']}")
    L.append(f"Task: normal vs abnormal   India(IN-CXR): {r['n_indian']}   West(CheXpert): {r['n_western']}")
    L.append("")
    L.append("ACCURACY and DELTA (West - India; positive = worse on Indian data)")
    L.append("-" * 70)
    L.append(f"{'Model':<28}{'India':>9}{'West':>9}{'Delta':>9}{'Sens(IN)':>10}{'Spec(IN)':>10}")
    for m in r["models"].values():
        i, w, d = m["indian"], m["western"], m["delta"]
        def s(x): return f"{x:.3f}" if x is not None else "n/a"
        def sd(x): return f"{x:+.3f}" if x is not None else "n/a"
        L.append(f"{m['label']:<28}{s(i['accuracy']):>9}{s(w['accuracy']):>9}"
                 f"{sd(d['accuracy_delta']):>9}{s(i['sensitivity']):>10}{s(i['specificity']):>10}")
    L.append("")
    L.append("Sens(IN)=sensitivity on Indian abnormal cases (did it catch disease).")
    L.append("Spec(IN)=specificity on Indian normal cases (did it avoid false alarms).")
    return "\n".join(L)


if __name__ == "__main__":
    main()
