"""
The prompt sent to every model, identical across all of them.

Keeping the prompt identical across models is what makes the comparison fair.
Keeping it identical across the Indian and Western datasets is what isolates
population as the variable. Do not customize per model or per dataset.

PRIMARY TASK: classify the chest X-ray as normal or abnormal.
"""

SYSTEM_PROMPT = (
    "You are an expert radiologist interpreting a frontal chest X-ray. "
    "Decide whether the radiograph is NORMAL (no significant abnormality) or "
    "ABNORMAL (any significant abnormality present). "
    "Respond with valid JSON only, no preamble, no explanation."
)


def build_user_prompt() -> str:
    return (
        "Assess this chest X-ray. Return ONLY a JSON object of this exact shape:\n\n"
        "{\n"
        '    "assessment": "normal|abnormal",\n'
        '    "confidence": "high|medium|low"\n'
        "}\n\n"
        "Choose 'abnormal' if you see any significant abnormality (consolidation, "
        "effusion, cardiomegaly, opacity, pneumothorax, edema, TB-related changes, "
        "or any other significant finding). Choose 'normal' only if the film shows "
        "no significant abnormality. Do not add keys beyond those listed. "
        "Do not include any text outside the JSON object."
    )


# ---------------------------------------------------------------------------
# REPORT GENERATION (option B: radiologist-style narrative report)
# ---------------------------------------------------------------------------
REPORT_SYSTEM_PROMPT = (
    "You are an experienced radiologist reporting a frontal chest X-ray. "
    "Write a concise, professional radiology report as you would for the "
    "ordering physician. Be specific about findings and their location. "
    "Do not hedge unnecessarily. Respond with valid JSON only."
)


def build_report_prompt() -> str:
    return (
        "Report this chest X-ray. Return ONLY a JSON object of this exact shape:\n\n"
        "{\n"
        '    "findings": "<your detailed findings: what you observe in each '
        'zone, any abnormality, location and character>",\n'
        '    "impression": "<your concise clinical impression / conclusion>",\n'
        '    "normal_or_abnormal": "normal|abnormal"\n'
        "}\n\n"
        "Write findings and impression as a real radiologist would. "
        "Do not include any text outside the JSON object."
    )
