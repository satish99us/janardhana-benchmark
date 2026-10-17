# RUN THIS BENCHMARK — instructions for the Cursor agent

You (the agent) are running a chest X-ray report-quality benchmark on the user's
**personal laptop**. A cheap fast coding model (e.g. Composer) is fine for this —
the work is mechanical command execution. Follow the steps; stop and ask the user
only when a step needs their input.

## THE USER DOES ONLY TWO THINGS (everything else is YOUR job):
  1. Puts three fresh API keys into `.env` (only ANTHROPIC_API_KEY is needed for
     the pilot; the other two are disabled in config for now).
  2. Downloads two IN-CXR subsets from the NIRT portal (one normal, one abnormal)
     and drops them in:  downloads/incxr-normal/  and  downloads/incxr-abnormal/

## YOU (the agent) do everything else:
  - install dependencies
  - pull a SMALL CheXpert frontal subset via AzCopy (NOT the full 11GB — see Step 2)
  - convert the IN-CXR DICOMs to PNG
  - build balanced manifests (50 normal + 50 abnormal each side)
  - generate reports with ONE model (Claude — pilot config)
  - build the blinded grading packet for the radiologist
  - (later, after the radiologist returns grades) score them

## PILOT SCOPE (already set in src/config.py):
  - ONE model (Claude). gpt + gemini are disabled — enable later for the full run.
  - 50 Indian + 50 Western images. ~100 reports for the radiologist to grade.
  - This is a PILOT to see if the gap is real, fast and cheap. Do NOT deploy to
    any cloud. Everything stays local. The radiologist grades from a local HTML
    file; medical images never leave the user's machine.

---

## Step 0 — Environment

Confirm Python 3.10+ is installed. Create and activate a virtual environment in
the project root, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 1 — API keys

Ask the user to create the `.env` file from the template and paste their FRESH
keys (the old ones were exposed and revoked):

```bash
cp .env.example .env
```

Then the user edits `.env` and fills in ANTHROPIC_API_KEY, OPENAI_API_KEY,
GEMINI_API_KEY. Do NOT print the keys back. `.env` is gitignored.

Also: open `src/config.py` and confirm the three `model_id` strings match the
exact current model versions the user's keys can access. Update if needed.

---

## Step 2 — Download a SMALL CheXpert subset (Western baseline)

The user has a time-limited Stanford Azure SAS link. We need only ~100-200
frontal images for the pilot, NOT the full 11GB. Use AzCopy with patterns to
pull a bounded subset.

1. Install AzCopy (https://aka.ms/downloadazcopy ; macOS: `brew install azcopy`).
2. Ask the user to paste their CheXpert SAS link locally (it is a credential —
   never commit it; it expires).
3. First pull just the label CSV (small), then a bounded set of frontal images:

```bash
# label CSV (valid.csv is smaller than train.csv — prefer it)
azcopy copy "<SAS_LINK_TO_valid.csv>" "./downloads/chexpert/" 
# a bounded set of frontal images — limit so we don't pull 11GB
azcopy copy "<SAS_LINK>" "./downloads/chexpert/" --recursive --include-pattern "*frontal*" --list-of-files /dev/null 2>/dev/null || azcopy copy "<SAS_LINK>" "./downloads/chexpert/" --recursive --include-pattern "*frontal*"
```

If AzCopy subset patterns are awkward with the given SAS scope, the simplest
robust fallback: pull the `valid` split only (it is a few hundred images, not
the full train set) by pointing the SAS path at the valid folder. We only need
~100 frontal images total; prepare_chexpert.py will select a balanced 50/50 from
whatever is present. Do NOT pull the entire 11GB train set.

---

## Step 3 — IN-CXR (Indian dataset) — USER DOES THIS

The user downloads two IN-CXR subsets from the NIRT portal (one normal subset,
one abnormal subset, each a few hundred DICOM images) and places them in:
  downloads/incxr-normal/      (normal DICOMs)
  downloads/incxr-abnormal/    (abnormal DICOMs)
Confirm these two folders exist and contain files before continuing.

---

## Step 4 — Convert IN-CXR DICOMs to PNG

IN-CXR ships as **DICOM** files. The model APIs need PNG/JPG, so convert first.
The user downloaded one normal bundle (~307 images) and one abnormal bundle
(~377 images). Convert each into a normal/ and abnormal/ PNG folder:

```bash
python -m src.convert_dicom ./downloads/incxr-normal ./downloads/incxr-png/normal
python -m src.convert_dicom ./downloads/incxr-abnormal ./downloads/incxr-png/abnormal
```

(Adjust the input paths to wherever the user's normal and abnormal DICOM bundles
actually live.) The converter applies proper windowing so the PNGs look like real
radiographs.

CheXpert already ships as JPG — no conversion needed.

## Step 5 — Build the balanced manifests

These scripts copy a balanced working set into `data/` and write the manifests.
Sampling is balanced (equal normal/abnormal) — critical, because IN-CXR is ~93%
normal and a naive sample would be meaningless.

```bash
# Indian: point at the converted PNG folders
python -m src.prepare_incxr --normal ./downloads/incxr-png/normal --abnormal ./downloads/incxr-png/abnormal

# Western: point at the CheXpert root (finds the label CSV, collapses to normal/abnormal)
python -m src.prepare_chexpert ./downloads/chexpert
```

After this, `data/indian/manifest.csv` and `data/chexpert/manifest.csv` exist,
each with balanced normal/abnormal rows.

---

## Step 6 — Run the benchmark

```bash
python -m src.run_benchmark
```

This makes live paid API calls (the user's keys). Default is 30 normal + 30
abnormal per dataset = 60 images/dataset, ~120 calls per model. Cost is small
(a few hundred rupees). Let it finish; it prints a summary table and writes:
- `results/benchmark_<timestamp>.json`  ← the full result
- `results/summary_<timestamp>.txt`     ← readable table

---

## Step 7 — Hand back the result

Print the contents of the summary table, and tell the user to copy the full
contents of the `results/benchmark_<timestamp>.json` file and paste it back to
Claude in chat for interpretation and next steps.

Do NOT paste the API keys or the CheXpert SAS link into chat or commit them.

---

## What the result means (for context)

- **accuracy_delta** = West accuracy − India accuracy. Positive = the model is
  worse on Indian X-rays. A consistent positive delta (~+0.08 to +0.15) across
  all three models supports the thesis that Indian data matters.
- **sensitivity on Indian abnormal cases** = did the model catch real disease.
- If the delta is near zero, the thesis (as stated) isn't supported on this
  task — which is itself valuable to know now.

That's the whole job: set up, download both datasets, build balanced manifests,
run, return the JSON.

---

# OPTION B — radiologist-graded report quality (the richer study)

This is the upgraded workflow: models GENERATE radiologist-style reports for
both Indian and Western X-rays, a radiologist grades them BLIND (not knowing
model or which dataset), and we compute the India-vs-West quality gap.

Run AFTER datasets are prepared (Steps 0-5 above give you data/indian and
data/chexpert with manifests).

## B1 — generate reports
```bash
python -m src.generate_reports
```
Writes results/reports_<stamp>.json (reports for both datasets, with hidden
model/dataset labels).

## B2 — build the blinded grading packet
```bash
python -m src.build_grading_packet reports_<stamp>.json
```
Creates `grading_packet/` (blinded images + grade.html + csv) and a HIDDEN key
`results/_key_<stamp>.json`. 
- Give the radiologist the WHOLE `grading_packet/` folder only.
- NEVER give them the _key file. That's what makes it blind.

## B3 — radiologist grades
The radiologist opens `grading_packet/grade.html` in any browser, reviews each
X-ray + report, fills the rubric (main finding caught? dangerous miss?
hallucination? overall soundness 1-5?), clicks "Download grades.json", and sends
that file back.

Framing for the radiologist: "This is human + AI work — please grade honestly,
make no assumptions about how it was produced." (True, and it keeps them unbiased.)

For a publishable result later, have a SECOND radiologist grade an overlapping
subset so you can report inter-rater agreement.

## B4 — score
```bash
python -m src.score_grades grades.json _key_<stamp>.json
```
Writes results/grading_result.json with the India-vs-West gap per rubric axis.
Paste that JSON back to Claude.
