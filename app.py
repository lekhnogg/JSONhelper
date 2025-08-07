import streamlit as st
from json_repair import repair_json
import json, re
from jsonschema import Draft7Validator

st.set_page_config(page_title="JSON Repair + Schema Validate", layout="wide")
st.title("JSON Repair + Schema Validate")

RAW = st.text_area(
    "Paste broken JSON here",
    height=240,
    placeholder='{"explanation":"Overall notes: None. relevancy explanation: No comment. ..."}',
)

SCHEMA_TXT = st.text_area(
    "Paste Draft-07 JSON Schema here",
    height=240,
    placeholder='{"$schema":"http://json-schema.org/draft-07/schema#","type":"object"}',
)

# ---- Labels to promote from `explanation` -> top-level fields ----
LABELS = {
    r"overall\s*notes": "overall_notes",
    r"relevancy\s*explanation": "relevancy_explanation",
    r"originality\s*explanation": "originality_explanation",
    r"distinct[_\s-]*answers\s*explanation": "distinct_answers_explanation",
    r"self[_\s-]*containment\s*explanation": "self_containment_explanation",
    r"initial\s*answer\s*rationale": "initial_answer_rationale",
    r"rationale\s*(?:or\s*defense)?\s*after\s*seeing\s*original\s*author'?s\s*correct\s*answer": "rationale_after_oa",
    r"citation\s*accuracy": "citation_accuracy",
    r"citation\s*rationale": "citation_rationale",
}
# Match label (case-insensitive), allowing it to appear after punctuation or immediately after text,
# and capture through the colon. Content starts at match.end().
LABEL_REGEX = re.compile(
    r"(?is)(?:^|[^\w])(" + "|".join(LABELS.keys()) + r")\s*:\s*"
)

def extract_sections(text: str):
    matches = list(LABEL_REGEX.finditer(text))
    out = {}
    if not matches:
        return out, text.strip() or None

    def map_label(key_pat: str) -> str:
        for pat, field in LABELS.items():
            if re.fullmatch(pat, key_pat, flags=re.IGNORECASE):
                return field
        return None

    for i, m in enumerate(matches):
        key_pat = m.group(1)
        start = m.end()  # after the colon
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[start:end].strip()
        # Normalize trailing punctuation and whitespace
        value = re.sub(r"\s+", " ", value).rstrip()
        # Drop trailing lone periods if desired
        value = value.rstrip()
        field = map_label(key_pat)
        if field:
            out[field] = value or None

    # Any leftover outside labeled blocks
    prefix = text[:matches[0].start()].strip()
    suffix = text[matches[-1].end():].strip()
    residual = " ".join(s for s in (prefix, suffix) if s).strip() or None
    return out, residual

# ---- Default schema (you can paste your own) ----
DEFAULT_SCHEMA = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Review Payload",
  "type": "object",
  "additionalProperties": False,
  "required": [
    "reviewer_type","reviewer_title","answer","answer_index",
    "est_time_answer","est_grade_level","est_difficulty_given_grade_level","explanation"
  ],
  "properties": {
    "reviewer_type": {"type":"string","enum":["R1/R2","R3"]},
    "reviewer_title": {"type":"string","minLength":1},
    "answer": {
      "oneOf": [
        {"type":"array","items":{"type":"string","pattern":"^[A-Z]$"},"minItems":1},
        {"type":"string","pattern":"^[A-Z]$"}
      ]
    },
    "answer_index": {
      "oneOf": [
        {"type":"array","items":{"type":"integer","minimum":0},"minItems":1},
        {"type":"integer","minimum":0}
      ]
    },
    "est_time_answer": {"type":["string","null"]},
    "est_grade_level": {"type":["string","null"]},
    "est_difficulty_given_grade_level": {"type":["string","null"]},
    "explanation": {"type":"string","minLength":1},

    # Promoted (optional)
    "overall_notes": {"type":["string","null"]},
    "relevancy_explanation": {"type":["string","null"]},
    "originality_explanation": {"type":["string","null"]},
    "distinct_answers_explanation": {"type":["string","null"]},
    "self_containment_explanation": {"type":["string","null"]},
    "initial_answer_rationale": {"type":["string","null"]},
    "rationale_after_oa": {"type":["string","null"]},
    "citation_accuracy": {"type":["string","null"]},
    "citation_rationale": {"type":["string","null"]},
    "explanation_residual": {"type":["string","null"]}
  },
  "allOf": [
    {"oneOf":[
      {"properties":{"reviewer_type":{"enum":["R1/R2"]},"answer":{"type":"array"},"answer_index":{"type":"array"}},
       "required":["reviewer_type","answer","answer_index"]},
      {"properties":{"reviewer_type":{"enum":["R3"]},"answer":{"type":"string"},"answer_index":{"type":"integer"}},
       "required":["reviewer_type","answer","answer_index"]}
    ]}
  ]
}

if st.button("Repair → Promote → Validate → Pretty-print"):
    try:
        fixed = repair_json(RAW or "")
        data = json.loads(fixed)
    except Exception as e:
        st.error(f"Repair/parse failed: {e}")
    else:
        st.success("JSON repaired and parsed.")

        # Promote labeled sections from `explanation`
        if isinstance(data.get("explanation"), str):
            sections, residual = extract_sections(data["explanation"])
            data.update(sections)
            data["explanation_residual"] = residual

        # Schema: use pasted one if provided, else default
        schema_txt = SCHEMA_TXT.strip() or json.dumps(DEFAULT_SCHEMA)
        try:
            schema = json.loads(schema_txt)
        except Exception as e:
            st.warning(f"Schema parse failed; using default. Error: {e}")
            schema = DEFAULT_SCHEMA

        # Validate
        try:
            errs = sorted(Draft7Validator(schema).iter_errors(data), key=lambda e: e.path)
            if errs:
                st.error("Schema validation errors:")
                for e in errs:
                    path = "/".join(map(str, e.path)) or "<root>"
                    st.write(f"- **{path}**: {e.message}")
            else:
                st.success("Valid against schema ✅")
        except Exception as e:
            st.error(f"Schema validation failed: {e}")

        # Outputs
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Pretty JSON (promoted)")
            st.json(data)
        with col2:
            st.subheader("Repaired JSON (raw text)")
            st.code(fixed, language="json")
