import json
from pathlib import Path

def load_fixture(name: str):
    p = Path(__file__).resolve().parents[1] / "fixtures" / name
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def load_all_fixtures():
    ctx = load_fixture("sample_context.json")
    claims = load_fixture("sample_claims.json")
    meta = load_fixture("sample_metadata.json")
    return {"context": ctx, "claims": claims, "metadata": meta}
