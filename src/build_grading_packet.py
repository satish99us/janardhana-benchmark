"""
STEP 2 of option B: build a BLINDED grading packet for the radiologist.

Takes the generated reports, strips everything identifying (model name, which
dataset, the truth label), shuffles them, copies the images under blind IDs, and
produces:

  grading_packet/
    images/                 blinded images (blind_id.png)
    grade.html              the grading interface the radiologist uses
    grading_sheet.csv       a fallback they can fill in a spreadsheet
  results/_key_<stamp>.json HIDDEN key (blind_id -> dataset/model/truth) — do
                            NOT give this to the radiologist.

The radiologist opens grade.html, views each image + report, fills the rubric,
and clicks "Download grades" -> grades.json, which they send back to you.

USAGE:  python -m src.build_grading_packet reports_<stamp>.json
"""

import sys
import json
import random
import shutil
from pathlib import Path
from .config import RESULTS, DATA_INDIAN, DATA_CHEXPERT, RUBRIC

random.seed(7)
PACKET = RESULTS.parent / "grading_packet"


def _find_image(case_id: str, dataset: str) -> Path:
    folder = DATA_INDIAN if dataset == "indian" else DATA_CHEXPERT
    p = folder / case_id
    return p if p.exists() else None


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.build_grading_packet reports_<stamp>.json")
        sys.exit(1)
    reports_file = RESULTS / sys.argv[1]
    if not reports_file.exists():
        reports_file = Path(sys.argv[1])
    data = json.loads(reports_file.read_text())
    records = data["records"]

    # shuffle and assign blind IDs
    random.shuffle(records)
    PACKET.mkdir(parents=True, exist_ok=True)
    (PACKET / "images").mkdir(exist_ok=True)

    key = {}        # blind_id -> hidden truth
    packet_items = []  # what the radiologist sees (no hidden fields)
    for idx, rec in enumerate(records):
        blind_id = f"CASE{idx:04d}"
        src = _find_image(rec["case_id"], rec["dataset"])
        if not src:
            continue
        ext = src.suffix.lower()
        dst = PACKET / "images" / f"{blind_id}{ext}"
        shutil.copy(src, dst)
        key[blind_id] = {
            "dataset": rec["dataset"],
            "model": rec["model"],
            "model_label": rec["model_label"],
            "case_id": rec["case_id"],
            "truth_label": rec["truth_label"],
            "report_id": rec["report_id"],
        }
        packet_items.append({
            "blind_id": blind_id,
            "image": f"images/{blind_id}{ext}",
            "findings": rec["report"].get("findings", ""),
            "impression": rec["report"].get("impression", ""),
        })

    # hidden key (kept in results/, NOT in packet)
    stamp = reports_file.stem.replace("reports_", "")
    key_file = RESULTS / f"_key_{stamp}.json"
    key_file.write_text(json.dumps(key, indent=2))

    # CSV fallback
    _write_csv(packet_items)
    # HTML interface
    _write_html(packet_items)

    print(f"Blinded packet built: {PACKET}")
    print(f"  - {len(packet_items)} reports to grade")
    print(f"  - give the radiologist the WHOLE grading_packet/ folder")
    print(f"  - hidden key (do NOT share): {key_file}")
    print(f"\nRadiologist opens grading_packet/grade.html, grades, downloads grades.json.")
    print(f"Then: python -m src.score_grades grades.json _key_{stamp}.json")


def _write_csv(items):
    import csv
    cols = ["blind_id"] + list(RUBRIC.keys()) + ["notes"]
    with open(PACKET / "grading_sheet.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for it in items:
            w.writerow([it["blind_id"]] + ["" for _ in RUBRIC] + [""])


def _write_html(items):
    rubric_json = json.dumps(RUBRIC)
    items_json = json.dumps(items)
    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Chest X-ray Report Review</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:24px;color:#1a1a1a;}
 h1{font-size:22px;} .sub{color:#555;margin-bottom:24px;}
 .case{border:1px solid #ddd;border-radius:10px;padding:18px;margin-bottom:22px;}
 .case h3{margin:0 0 12px;}
 .toprow{display:flex;gap:20px;flex-wrap:wrap;}
 .imgwrap{flex:1;min-width:320px;} .imgwrap img{width:100%;border-radius:8px;background:#000;}
 .ownwrap{flex:1;min-width:320px;}
 .rep{margin-top:16px;border-top:2px dashed #bbb;padding-top:12px;}
 .revealbtn{margin-top:10px;background:#444;color:#fff;border:0;padding:9px 16px;border-radius:6px;cursor:pointer;font-size:13px;}
 .rep .lbl{font-weight:600;font-size:13px;color:#444;margin-top:8px;}
 .rep .txt{white-space:pre-wrap;background:#f6f6f6;padding:10px;border-radius:6px;font-size:14px;}
 .q{margin:14px 0 4px;font-size:14px;font-weight:600;}
 .opts label{margin-right:14px;font-size:14px;cursor:pointer;}
 textarea{width:100%;min-height:48px;margin-top:6px;}
 .bar{position:sticky;bottom:0;background:#fff;border-top:1px solid #ddd;padding:14px 0;text-align:center;}
 button{background:#0e6b5f;color:#fff;border:0;padding:12px 28px;border-radius:8px;font-size:15px;cursor:pointer;}
 .prog{font-size:13px;color:#555;margin-bottom:8px;}
</style></head><body>
<h1>Chest X-ray Report Review</h1>
<p class="sub">This is human + AI work. Please review each report against the X-ray and grade it honestly,
making no assumptions about how it was produced. Your unbiased clinical judgement is what we need.
Grades stay in your browser until you click Download at the bottom.</p>
<div id="cases"></div>
<div class="bar"><div class="prog" id="prog"></div>
<button onclick="dl()">Download grades.json</button></div>
<script>
const RUBRIC=__RUBRIC__; const ITEMS=__ITEMS__; const grades={};
const root=document.getElementById('cases');
ITEMS.forEach(it=>{
 const d=document.createElement('div');d.className='case';
 let q='';
 for(const [k,v] of Object.entries(RUBRIC)){
   q+=`<div class="q">${v.question}</div><div class="opts">`;
   v.options.forEach(o=>{q+=`<label><input type="radio" name="${it.blind_id}_${k}" value="${o}" onchange="set('${it.blind_id}','${k}','${o}')"> ${o}</label>`;});
   q+=`</div>`;
 }
 d.innerHTML=`<h3>${it.blind_id}</h3>
   <div class="toprow">
     <div class="imgwrap"><img src="${it.image}"></div>
     <div class="ownwrap">
       <div class="q">Your own reading FIRST (record this before revealing the report):</div>
       <textarea placeholder="Your findings / impression for this X-ray" onchange="setOwn('${it.blind_id}',this.value)"></textarea>
       <button type="button" class="revealbtn" onclick="reveal('${it.blind_id}')">I have recorded my reading &mdash; reveal the report to grade &darr;</button>
     </div>
   </div>
   <div class="rep" id="rep_${it.blind_id}" style="display:none">
     <div class="lbl">REPORT TO GRADE</div>
     <div class="lbl">FINDINGS</div><div class="txt">${it.findings||'(none)'}</div>
     <div class="lbl">IMPRESSION</div><div class="txt">${it.impression||'(none)'}</div>
     ${q}<div class="q">Notes on this report (optional)</div><textarea onchange="setN('${it.blind_id}',this.value)"></textarea>
   </div>`;
 root.appendChild(d);
});
function set(id,k,v){grades[id]=grades[id]||{};grades[id][k]=v;prog();}
function setN(id,v){grades[id]=grades[id]||{};grades[id].notes=v;}
function setOwn(id,v){grades[id]=grades[id]||{};grades[id].own_reading=v;}
function reveal(id){document.getElementById('rep_'+id).style.display='block';}
function prog(){const done=Object.keys(grades).filter(id=>Object.keys(RUBRIC).every(k=>grades[id]&&grades[id][k])).length;
 document.getElementById('prog').textContent=done+' / '+ITEMS.length+' cases fully graded';}
function dl(){const blob=new Blob([JSON.stringify(grades,null,2)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='grades.json';a.click();}
prog();
</script></body></html>"""
    html = html.replace("__RUBRIC__", rubric_json).replace("__ITEMS__", items_json)
    (PACKET / "grade.html").write_text(html)


if __name__ == "__main__":
    main()
