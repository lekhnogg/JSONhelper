import streamlit as st
from json_repair import repair_json
import json
from jsonschema import Draft7Validator

st.set_page_config(page_title="JSON Repair + Schema Validate", layout="wide")

st.title("JSON Repair + Schema Validate")

RAW = st.text_area("Paste broken JSON here", height=220, placeholder='{"explanation":"classic "pendulum and peg" …"}')
SCHEMA_TXT = st.text_area("Paste Draft-07 JSON Schema here", height=220, placeholder='{"$schema":"http://json-schema.org/draft-07/schema#","type":"object"}')

MAX_WORDS_PER_LINE = st.slider("Wrap long strings every N words", 20, 80, 24)

def wrap_words(s, n=24):
    w = s.split()
    return "\n".join(" ".join(w[i:i+n]) for i in range(0, len(w), n))

def wrap_strings(obj, n=24):
    if isinstance(obj, dict):
        return {k: wrap_strings(v, n) for k, v in obj.items()}
    if isinstance(obj, list):
        return [wrap_strings(v, n) for v in obj]
    if isinstance(obj, str):
        return wrap_words(s=obj, n=n)
    return obj

col1, col2 = st.columns(2)
if st.button("Repair → Validate → Pretty-print"):
    try:
        fixed = repair_json(RAW or "")
        data = json.loads(fixed)
    except Exception as e:
        st.error(f"Repair/parse failed: {e}")
    else:
        st.success("JSON repaired and parsed.")
        st.code(fixed, language="json")

        # Validate if a schema was provided
        if SCHEMA_TXT.strip():
            try:
                schema = json.loads(SCHEMA_TXT)
                errs = sorted(Draft7Validator(schema).iter_errors(data), key=lambda e: e.path)
                if errs:
                    st.error("Schema validation errors:")
                    for e in errs:
                        path = "/".join(map(str, e.path)) or "<root>"
                        st.write(f"- **{path}**: {e.message}")
                else:
                    st.success("Valid against schema ✅")
            except Exception as e:
                st.warning(f"Schema not valid/parsing failed: {e}")

        with col1:
            st.subheader("Pretty JSON")
            st.json(data)

        with col2:
            st.subheader("Wrapped JSON (easier to read)")
            wrapped = wrap_strings(data, MAX_WORDS_PER_LINE)
            st.code(json.dumps(wrapped, ensure_ascii=False, indent=2), language="json")
