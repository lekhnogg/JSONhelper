import streamlit as st
from json_repair import repair_json
import json, re
from jsonschema import Draft7Validator

st.set_page_config(page_title="Multi JSON Repair + Schema Validate", layout="wide")
st.title("Multi JSON Repair + Schema Validate")

EXAMPLE = """reviewer
{"reviewer_type":"R1/R2","reviewer_title":"No title at this time.","answer":["A"],"answer_index":[0],"est_time_answer":"LESS_THAN_FIVE_MINUTES","est_grade_level":"UNDERGRADUATE_YEAR_3","est_difficulty_given_grade_level":"EASY","explanation":"Overall notes: All good. relevancy explanation: No comment. originality explanation: No comment. distinct_answers explanation: No comment. self_containment explanation: No comment.Initial answer rationale: plug into the vis-viva equation. Rationale or defense after seeing original author's correct answer: No comment. Citation accuracy: No citation accuracy provided. Citation rationale: No citation rationale provided. "}
reviewer
{"reviewer_type":"R1/R2","reviewer_title":"Research Scientist","answer":["A"],"answer_index":[0],"est_time_answer":"FIVE_MINUTES","est_grade_level":"GRADUATE_YEAR_1","est_difficulty_given_grade_level":"MEDIUM","explanation":"Overall notes: All points have been addressed relevancy explanation: No comment. originality explanation: No comment. distinct_answers explanation: No comment. self_containment explanation: No comment.Initial answer rationale: A is correct because applying conservation laws in orbital mechanics gives the satellite's speed at perigee as 3*v/sqrt(5) This explanation is logical Citation accuracy: No citation accuracy provided. Citation rationale: No citation rationale provided. "}
reviewer
{"reviewer_type":"R3","reviewer_title":"None","answer":"A","answer_index":0,"est_time_answer":null,"est_grade_level":null,"est_difficulty_given_grade_level":null,"explanation":"Overall notes: R1 and R2 both agree with the OA’s reasoning. Accepting. relevancy explanation: No comment. originality explanation: No comment. distinct_answers explanation: No comment. self_containment explanation: No comment.Initial answer rationale: No initial answer rationale provided. Rationale or defense after seeing original author's correct answer: No comment. Citation accuracy: No citation accuracy provided. Citation rationale: No citation rationale provided. "}
reviewer
{"reviewer_type":"R3","reviewer_title":"None","answer":"A","answer_index":0,"est_time_answer":null,"est_grade_level":null,"est_difficulty_given_grade_level":null,"explanation":"Overall notes: Adjusted subtopic relevancy explanation: No comment. originality explanation: No comment. distinct_answers explanation: No comment. self_containment explanation: No comment.Initial answer rationale: No initial answer rationale provided. Rationale or defense after seeing original author's correct answer: No comment. Citation accuracy: No citation accuracy provided. Citation rationale: No citation rationale provided. "}"""

RAW_MULTI = st.text_area(
    "Paste up to 4 segments in the format:  reviewer  + newline +  {json}",
    height=320,
    value=EXAMPLE
)

SCHEMA_TXT = st.text_area(
    "Paste Draft-07 JSON Schema here (or leave blank to use default)",
    height=200,
    placeholder='{"$schema":"http://json-schema.org/draft-07/schema#","type":"object"}'
)

# ---------- Promotion rules ----------
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
LABEL_REGEX = re.compile(r"(?is)(?:^|[^\w])(" + "|".join(LABELS.keys()) + r")\s*:\s*")

PLACEHOLDER_PATTERNS = [
    r"no\s*comment\.?$",
    r"none\.?$",
    r"no\s*initial\s*answer\s*rationale\s*provided\.?$",
    r"no\s*citation\s*accuracy\s*provided\.?$",
    r"no\s*citation\s*rationale\s*provided\.?$"
]
PLACEHOLDER_REGEX = re.compile(r"(?is)^(?:\s*(?:" + "|".join(PLACEHOLDER_PATTERNS) + r")\s*)$")

def _is_placeholder(s: str) -> bool:
    return bool(PLACEHOLDER_REGEX.match((s or "").strip()))

def extract_sections(text: str):
    matches = list(LABEL_REGEX.finditer(text))
    out = {}
    if not matches:
        return out, (text.strip() or None)

    def map_label(key_pat: str) -> str:
        for pat, field in LABELS.items():
            if re.fullmatch(pat, key_pat, flags=re.IGNORECASE):
                return field
        return None

    for i, m in enumerate(matches):
        key_pat = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[start:end].strip()
        value = re.sub(r"\s+", " ", value).strip()
        field = map_label(key_pat)
        if field:
            out[field] = None if (not value or _is_placeholder(value)) else value

    prefix = text[:matches[0].start()].strip()
    suffix = text[matches[-1].end():].strip()
    residual_chunks = " ".join(s for s in (prefix, suffix) if s).strip()
    residual = residual_chunks if residual_chunks else None
    if isinstance(residual, str) and _is_placeholder(residual):
        residual = None
    return out, residual

# ---------- Default Draft-07 schema ----------
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
    "explanation": {"type":["string","null"]},

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

def split_segments(blob: str, limit: int = 4):
    # Split on lines that contain only 'reviewer' (case-insensitive, surrounding whitespace allowed)
    parts = re.split(r"(?im)^\s*reviewer\s*$", blob.strip())
    # After split, parts[0] may be empty header; keep non-empty JSON-ish chunks
    chunks = [p.strip() for p in parts if p.strip()]
    return chunks[:limit]

def process_one(raw_json_text: str, schema: dict):
    # 1) Repair & parse
    fixed = repair_json(raw_json_text or "")
    data = json.loads(fixed)

    # 2) Promote & replace explanation with residual (avoid duplication)
    if isinstance(data.get("explanation"), str):
        sections, residual = extract_sections(data["explanation"])
        data.update(sections)
        data["explanation_residual"] = residual
        data["explanation"] = residual

    # 3) Validate
    errors = sorted(Draft7Validator(schema).iter_errors(data), key=lambda e: e.path)
    return fixed, data, errors

if st.button("Process All"):
    try:
        schema_txt = SCHEMA_TXT.strip() or json.dumps(DEFAULT_SCHEMA)
        schema = json.loads(schema_txt)
    except Exception as e:
        st.warning(f"Schema parse failed; using default. Error: {e}")
        schema = DEFAULT_SCHEMA

    segments = split_segments(RAW_MULTI)
    if not segments:
        st.info("No segments detected. Be sure to include lines that contain only the word 'reviewer' before each JSON block.")
    else:
        for i, seg in enumerate(segments, 1):
            st.markdown(f"### Segment {i}")
            try:
                fixed, data, errs = process_one(seg, schema)
            except Exception as e:
                st.error(f"Segment {i}: repair/parse failed → {e}")
                st.code(seg, language="json")
                continue

            if errs:
                st.error("Schema validation errors:")
                for e in errs:
                    path = "/".join(map(str, e.path)) or "<root>"
                    st.write(f"- **{path}**: {e.message}")
            else:
                st.success("Valid against schema ✅")

            cols = st.columns(2)
            with cols[0]:
                st.subheader("Pretty JSON (promoted)")
                st.json(data)
            with cols[1]:
                st.subheader("Repaired JSON (raw text)")
                st.code(fixed, language="json")

        if len(segments) > 4:
            st.warning("Only the first 4 segments were processed.")
