# VALIDATION + MULTI-MODEL RUN — instructions for Claude (Opus 4.8) in Cursor

You are running inside the user's `janardhana-benchmark` project in Cursor, with
full access to the files, the data folders, and the ability to run Python and
make API calls using the keys in `.env`.

CONTEXT: A pilot already ran. Claude (claude-opus-4-8) generated 120 reports
(60 Indian IN-CXR + 60 Western CheXpert). A quick normal/abnormal accuracy check
showed Claude scored 45% on Indian vs 73% on Western — a 28-point gap. BUT the
Indian *normal* cases scored only 9/30 (30%), which is WORSE than random chance
on a two-way choice. That is a red flag that part of the gap may be a PIPELINE
ARTIFACT (bad image conversion, mislabeling, or an over-"abnormal" bias), not a
genuine population gap.

Your job, IN THIS ORDER. Do not skip ahead to the multi-model run until the
artifact checks pass — running GPT and Gemini on a broken pipeline wastes money
and produces a misleading result.

---

## PART 1 — INVESTIGATE THE CULPRITS (do this first)

### 1A. Visually inspect the Indian normal images
The biggest risk is that DICOM→PNG conversion (windowing) degraded the Indian
images so they look strange and models over-call "abnormal."

- Open 8-10 of the converted Indian NORMAL PNGs in `data/indian/` (the ones the
  manifest labels normal).
- For each, actually LOOK at it (render/view the image). Report: do they look
  like clean, legible chest X-rays with normal brightness/contrast? Or do they
  look too dark, washed out, blown out, inverted (white/black reversed), or
  otherwise abnormal in APPEARANCE (not pathology)?
- Compare side by side with 8-10 converted Western (CheXpert) normal images in
  `data/chexpert/`. Do the two populations look comparably exposed, or do the
  Indian ones look visibly different in a way that's about image processing
  rather than anatomy?
- SHOW ME the images inline so I can see them too, and give your honest read.

### 1B. Check for inversion / windowing problems specifically
IN-CXR is DICOM. MONOCHROME1 vs MONOCHROME2 and window settings are the usual
culprits. 
- Pick 3 original Indian DICOMs (from `downloads/incxr-png/...`'s source, or the
  original `downloads/incxr-normal/` DICOMs) and check their PhotometricInterpretation,
  WindowCenter, WindowWidth, and whether RescaleSlope/Intercept were applied.
- Confirm the conversion in `src/convert_dicom.py` handled them correctly (bones
  should appear white, lungs dark — normal radiograph appearance). If any images
  are inverted or mis-windowed, that's a real bug — report it and propose a fix,
  but do NOT change files until I confirm.

### 1C. Read what Claude actually SAID on the misclassified Indian normals
- From `results/reports_*.json`, pull the Indian cases where truth_label=normal
  but Claude said abnormal.
- Show me 8-10 of these: the blinded image + Claude's actual `findings` and
  `impression` text.
- Tell me the pattern: is Claude hallucinating findings that aren't there
  (artifact/over-call), or is it describing real-looking features? Is it
  consistently citing the same kind of "finding" (e.g. always "increased
  opacity") that might be an image-quality artifact?

### 1D. Check label integrity
- Confirm the Indian normal/abnormal split came from the right source. IN-CXR
  files were named `*_Normal.dicom` and `*_Abnormal.dicom`. Verify the manifest
  labels match the filename source-of-truth, with no mix-up between classes.
- Confirm the CheXpert normal/abnormal collapse in `prepare_chexpert.py` is
  sensible (No Finding => normal; any positive finding => abnormal).

### 1E. Report a verdict on PART 1
Tell me clearly: is the 28-point gap likely (a) a real population signal, (b)
substantially a pipeline artifact, or (c) a mix? Give your evidence. If you find
a real bug (inversion, mis-windowing, mislabeling), propose the fix and STOP —
let me confirm before re-running. If the pipeline looks clean, proceed to Part 2.

---

## PART 2 — ENABLE GPT-5.5 AND GEMINI, RE-RUN, COMPARE

Only after Part 1 is clean (or fixed and re-confirmed):

### 2A. Enable all three models
- In `src/config.py`, set enabled=True for gpt and gemini (claude already True).
- Confirm the model IDs are current: claude-opus-4-8, gpt-5.5-2026-04-23,
  gemini-3.1-pro-preview. If any errors as unavailable, query the provider API
  for the latest equivalent and use that (report what you chose).

### 2B. Regenerate reports for all three models
- Run `python -u -m src.generate_reports` (unbuffered so progress shows).
- This will generate reports for all enabled models on the same 60 Indian + 60
  Western images. Expect ~360 API calls total; it will take a while. It runs
  serially so rate limits are unlikely, but if you see repeated rate-limit
  errors, add a small sleep between calls and continue.
- Report failures per model.

### 2C. Run the normal/abnormal accuracy comparison for all three
- For each model, compute Indian accuracy, Western accuracy, and the gap, using
  the `normal_or_abnormal` field vs `truth_label` (same method as the pilot — no
  new API calls needed for scoring).
- Show me one clean table: rows = models (Claude, GPT-5.5, Gemini), columns =
  Indian acc, Western acc, gap, plus the normal-correct and abnormal-correct
  breakdown per model per dataset.

### 2D. Interpret
- Which models show the gap? Is it consistent across all three (suggps a real
  population effect) or does it vary wildly (suggests model-specific quirks)?
- Is the "worse on normals" pattern present for all three, or just Claude? If all
  three are worse-than-random on Indian normals, that strongly implies a pipeline
  artifact affecting the images, not three independent model failures.
- Give me your honest read.

---

## PART 3 — DO NOT (guardrails)
- Do NOT deploy anything to the cloud.
- Do NOT delete the existing reports JSON or the hidden `_key_*.json`.
- Do NOT paste API keys anywhere or print their values.
- Do NOT change `convert_dicom.py`, labels, or config without showing me the
  proposed change and getting my confirmation first.
- Keep all work local.

## OUTPUT I WANT AT THE END
1. A verdict on whether the 28-point Claude gap is real, artifact, or mixed (Part 1).
2. The three-model comparison table (Part 2).
3. Your honest interpretation of what the data shows — including whether the
   normal-case problem is a pipeline issue.
Be skeptical and rigorous. A real gap is good news for this project, but a false
gap built on a conversion bug would be worse than no result. Find the truth.
