# Janardhana Benchmark

**Does frontier AI underperform on Indian chest X-rays compared to Western ones?**

This project runs the same vision models (Claude, GPT-5, Gemini) on an Indian
chest X-ray dataset (IN-CXR / NIRT) and on a matched Western baseline (CheXpert),
using an identical prompt and identical scoring, and measures the **normal-vs-
abnormal accuracy gap** between the two populations. If models score materially worse on Indian patients for the same
findings at the same difficulty, that isolates *population* as the cause — which
is the core thesis of the data company.

This is a **preliminary signal tool**, not a publishable study. It tells you
fast and cheaply whether the gap is real before you invest in a rigorous,
radiologist-labeled study.

---

## What you need

1. **Fresh API keys** for Anthropic, OpenAI, and Google (Gemini). Put them in a
   local `.env` file (see below). Keys live only on your machine.
2. **Data**: a small set of Indian chest X-rays + a comparable CheXpert subset,
   each with a `manifest.csv`. See `data/indian/README.md` and
   `data/chexpert/README.md`.
3. Python 3.10+.

---

## Setup (in Cursor)

```bash
# 1. (optional but recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. create your .env from the template and paste your FRESH keys
cp .env.example .env
#    then open .env and paste your keys

# 4. add data
#    put images + manifest.csv in data/indian/ and data/chexpert/
#    (read the README in each folder)

# 5. run
python -m src.run_benchmark
```

You can also just tell the Cursor agent: *"run src/run_benchmark.py"* once the
`.env` and data are in place.

---

## What it does, step by step

1. Loads the Indian and Western datasets from their `manifest.csv` files.
2. For each model whose key is present in `.env`:
   - sends every image with an identical prompt asking for present/absent/uncertain
     across 8 findings,
   - collects structured JSON answers,
   - scores them against ground truth (sensitivity, specificity, accuracy per finding).
3. Computes the **West − India accuracy delta** per finding and overall.
4. Writes a timestamped JSON + a readable summary table into `results/`.

A **positive delta** means the model did worse on Indian data — the result that
supports the thesis.

---

## Reading the result

The summary prints a table like:

```
Model                          India      West     Delta
Claude (Anthropic)             0.742     0.831    +0.089
GPT-5 (OpenAI)                 0.715     0.824    +0.109
Gemini 2.5 Pro (Google)        0.760     0.838    +0.078
```

- **Delta around +0.08 to +0.15** across models → a real, consistent gap. Thesis
  supported. Time to design the rigorous study and start the Harrison / data
  conversations from a position of evidence.
- **Delta near zero** → the gap isn't there on average. Look at the per-finding
  table — the gap may live in specific findings (TB-related, etc.). That subgroup
  becomes your wedge. Better to learn this now than after a year of building.
- **Negative delta** → models do *better* on Indian data. Thesis as stated fails;
  rethink before building.

Then tell Claude the numbers and we interpret together and decide the next move.

---

## Cost & safety notes

- Start small. `MAX_CASES_PER_DATASET` in `src/config.py` defaults to 60. With
  ~60 cases × 2 datasets × 3 models that's ~360 API calls — a few hundred rupees
  at most. Scale up only after you see signal.
- The `.env` and the `data/` images are gitignored. Never commit them.
- If you ever expose a key, revoke it immediately and issue a new one.
- Update the exact model IDs in `src/config.py` to the current versions you have
  access to, and the run date is stamped automatically for reproducibility.

---

## Adding Harrison.rad.1 later

Harrison has no public batch API as of now (only the interactive app at
chat.harrison.ai). Two clean ways to add it:

1. **Ask Harrison for research/batch access** — start that conversation as a
   legitimate researcher; it also opens the customer relationship.
2. **Manual sample** — run 30–50 cases by hand through their app, record the
   outputs, and add them as a separate column reported transparently as a manual
   subset. Do **not** script/scrape their web app.

The `harrison` entry in `src/config.py` is already stubbed (disabled). Wire it
in once you have a real access path.

---

## Project layout

```
janardhana-benchmark/
├── README.md              ← you are here
├── requirements.txt
├── .env.example           ← copy to .env, add keys
├── .gitignore
├── src/
│   ├── config.py          ← findings, model versions, run size (tweak here)
│   ├── prompts.py         ← the identical prompt sent to every model
│   ├── clients.py         ← Claude / GPT / Gemini wrappers, one interface
│   ├── dataset.py         ← loads images + manifest.csv
│   ├── scoring.py         ← per-finding metrics + India-vs-West delta
│   └── run_benchmark.py   ← main entry point
├── data/
│   ├── indian/            ← your Indian images + manifest.csv (+ README)
│   └── chexpert/          ← Western baseline images + manifest.csv (+ README)
└── results/              ← timestamped outputs land here
```
