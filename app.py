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

    # Map a matched label to its canonical field
    def map_label(key_pat: str) -> str:
        for pat, field in LABELS.items():
            if re.fullmatch(pat, key_pat, flags=re.IGNORECASE):
                return field
        return None

    # Collect value spans to remove from residual
    spans = []
    for i, m in enumerate(matches):
        key_pat = m.group(1)
        field = map_label(key_pat)
        start_val = m.end()  # after "Label: "
        end_val = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[start_val:end_val].strip()
        value = re.sub(r"\s+", " ", value).strip()

        if field:
            out[field] = None if (not value or _is_placeholder(value)) else value
            # Remove the entire labeled block (label + value) from residual:
            spans.append((m.start(), end_val))
        else:
            # If somehow not mapped, at least remove its label token
            spans.append((m.start(), m.end()))

    # Build residual by keeping everything OUTSIDE labeled spans
    keep = []
    cursor = 0
    for s, e in sorted(spans):
        if cursor < s:
            keep.append(text[cursor:s])
        cursor = max(cursor, e)
    if cursor < len(text):
        keep.append(text[cursor:])

    residual = re.sub(r"\s+", " ", (" ".join(keep)).strip()) or None
    if isinstance(residual, str) and _is_placeholder(residual):
        residual = None

    # If residual accidentally equals any promoted value, clear it
    if residual and any(residual == v for v in out.values() if isinstance(v, str)):
        residual = None

    return out, residual

# ---------- Default Draft-07 schema (RELAXED to allow "no answer") ----------
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
        {"type":"array","items":{"type":"string","pattern":"^[A-Z]$"},"minItems":0},  # allow []
        {"type":"string","pattern":"^[A-Z]$"},
        {"type":"null"}  # allow null for "no answer" cases (e.g., R3)
      ]
    },
    "answer_index": {
      "oneOf": [
        {"type":"array","items":{"type":"integer","minimum":0},"minItems":0},  # allow []
        {"type":"integer","minimum":0},
        {"type":"null"}  # allow null for "no answer"
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
      # R1/R2 must use arrays (possibly empty after normalization)
      {"properties":{"reviewer_type":{"enum":["R1/R2"]},"answer":{"type":"array"},"answer_index":{"type":"array"}},
       "required":["reviewer_type","answer","answer_index"]},
      # R3 with concrete single answer
      {"properties":{"reviewer_type":{"enum":["R3"]},"answer":{"type":"string"},"answer_index":{"type":"integer"}},
       "required":["reviewer_type","answer","answer_index"]},
      # R3 explicitly unanswered
      {"properties":{"reviewer_type":{"enum":["R3"]},"answer":{"type":"null"},"answer_index":{"type":"null"}},
       "required":["reviewer_type","answer","answer_index"]}
    ]}
  ]
}

def split_segments(blob: str, limit: int = 4):
    parts = re.split(r"(?im)^\s*reviewer\s*$", blob.strip())
    chunks = [p.strip() for p in parts if p.strip()]
    return chunks[:limit]

# ---------- LaTeX brace protection ----------
BRACE_L = "__⟪LBRACE⟫__"
BRACE_R = "__⟪RBRACE⟫__"

def _protect_field_braces(raw: str, field_names=("explanation","initial_answer_rationale","rationale_after_oa")) -> str:
    pat = re.compile(
        r'("(?P<name>' + "|".join(map(re.escape, field_names)) + r')"\s*:\s*")(?P<val>(?:\\.|[^"\\])*)(")',
        flags=re.DOTALL
    )
    def repl(m):
        val = m.group("val").replace("{", BRACE_L).replace("}", BRACE_R)
        return m.group(1) + val + m.group(4)
    return pat.sub(repl, raw)

def _restore_braces_in_values(obj):
    def unmask(x):
        if isinstance(x, str):
            return x.replace(BRACE_L, "{").replace(BRACE_R, "}")
        return x
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            obj[k] = _restore_braces_in_values(v)
        return obj
    if isinstance(obj, list):
        return [_restore_braces_in_values(v) for v in obj]
    return unmask(obj)

# ---------- Normalize sentinel values like ["NONE"] and [-1] ----------
def _normalize_none_sentinels(d: dict):
    rt = (d.get("reviewer_type") or "").strip()
    ans = d.get("answer")
    idx = d.get("answer_index")

    if rt == "R1/R2":
        if isinstance(ans, list) and len(ans) == 1 and isinstance(ans[0], str) and ans[0].strip().upper() in ("NONE","N/A","NA"):
            d["answer"] = []  # empty = no selections
        if isinstance(idx, list) and len(idx) == 1 and isinstance(idx[0], int) and idx[0] < 0:
            d["answer_index"] = []  # empty = no indices
    elif rt == "R3":
        if isinstance(ans, str) and ans.strip().upper() in ("NONE","N/A","NA",""):
            d["answer"] = None
        if isinstance(idx, int) and idx < 0:
            d["answer_index"] = None
    return d

def process_one(raw_json_text: str, schema: dict):
    # Do NOT modify raw_json_text for the "Original Input" panel
    preprotected = _protect_field_braces(raw_json_text or "")
    repaired = repair_json(preprotected)  # repair for parsing/validation
    data = json.loads(repaired)

    # Restore braces and normalize NONE/-1
    data = _restore_braces_in_values(data)
    data = _normalize_none_sentinels(data)

    # Promote labeled sections from explanation
    if isinstance(data.get("explanation"), str):
        sections, residual = extract_sections(data["explanation"])
        data.update(sections)
        data["explanation_residual"] = residual
        data["explanation"] = residual

    # Validate
    errors = sorted(Draft7Validator(schema).iter_errors(data), key=lambda e: e.path)

    # For display, show the final, clean JSON (not the masked intermediate)
    fixed_display = json.dumps(data, ensure_ascii=False, indent=2)
    return fixed_display, data, errors

if st.button("Process All"):
    try:
        schema_txt = SCHEMA_TXT.strip() or json.dumps(DEFAULT_SCHEMA)
        schema = json.loads(schema_txt)
    except Exception as e:
        st.warning(f"Schema parse failed; using default. Error: {e}")
        schema = DEFAULT_SCHEMA

    segments = split_segments(RAW_MULTI)
    if not segments:
        st.info("No segments detected. Include lines that contain only the word 'reviewer' before each JSON block.")
    else:
        for i, seg in enumerate(segments, 1):
            st.markdown(f"### Segment {i}")
            try:
                fixed_text, data, errs = process_one(seg, schema)
            except Exception as e:
                st.error(f"Segment {i}: repair/parse failed → {e}")
                st.text_area("Original Input (as pasted)", value=seg, height=200, disabled=True, key=f"orig_err_{i}")
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
                st.subheader("Original Input (as pasted)")
                st.text_area("", value=seg, height=200, disabled=True, key=f"orig_{i}")
                st.subheader("Repaired JSON (final text)")
                st.code(fixed_text, language="json")

        if len(segments) > 4:
            st.warning("Only the first 4 segments were processed.")
