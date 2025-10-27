from typing import Iterable, Optional, List, Tuple
from config.config import db, logger, client
from app.utils.validators import normalize_event_path

def _get_claim_source_reference(event_id: str) -> Tuple[str, str]:
    path = normalize_event_path(event_id)
    info = db.collection(path).document("info").get()
    if not info.exists:
        raise RuntimeError(f"No 'info' in {path}")
    src = (info.to_dict() or {}).get("second_round_claims_source", {}) or {}
    col, doc = src.get("collection"), src.get("document")
    if not col or not doc:
        raise RuntimeError("Missing collection/document in second_round_claims_source")
    return col, doc

def _fetch_all_claim_texts(col: str, doc: str) -> List[str]:
    snap = db.collection(col).document(doc).get()
    if not snap.exists:
        return []
    claims = (snap.to_dict() or {}).get("claims", []) or []
    out = []
    for c in claims:
        t = (c or {}).get("text", "")
        if isinstance(t, str) and t.strip():
            out.append(t.strip())
    return out

def _select_agreeable_opposing(summary: str, bank: List[str]) -> str:
    body = "\n\n".join([f"[{i}] {t}" for i, t in enumerate(bank)])
    system_prompt = (
        "You will be given a user summary and a list of claim texts.\n"
        "Pick 2 claims that strongly agree and 2 that strongly oppose the user's view.\n"
        "Then add one sentence explaining why.\n"
        "Format:\n"
        "**Agreeable Claims:**\n- [index] text\n- [index] text\n\n"
        "**Opposing Claims:**\n- [index] text\n- [index] text\n\n"
        "**Reason:** <one sentence>"
    )
    user_prompt = f"User Summary:\n{summary}\n\nClaim Texts:\n{body}"
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_prompt}],
        temperature=0.4,
        max_tokens=1200,
    )
    return (resp.choices[0].message.content or "").strip()

def _parse_selection(block: str):
    agreeable, opposing, reason = [], [], None
    section = None
    for line in (block or "").splitlines():
        s = line.strip()
        if s.startswith("**Agreeable"):
            section = "A"; continue
        if s.startswith("**Opposing"):
            section = "O"; continue
        if s.startswith("**Reason:**"):
            reason = s.replace("**Reason:**", "").strip(); continue
        if s.startswith("- [") and "]" in s:
            if section == "A": agreeable.append(s)
            elif section == "O": opposing.append(s)
    return agreeable, opposing, (reason or "No reason provided.")

def select_and_store_for_event(event_id: str, only_for: Optional[Iterable[str]] = None) -> int:
    """Write agreeable_claims, opposing_claims, claim_selection_reason where missing."""
    col, doc = _get_claim_source_reference(event_id)
    bank = _fetch_all_claim_texts(col, doc)
    if not bank:
        logger.warning(f"[find_perspectives] empty claim bank {col}/{doc}")
        return 0

    
    path = normalize_event_path(event_id)
    coll = db.collection(path)

    docs = coll.stream() if not only_for else [coll.document(p).get() for p in only_for]
    updated = 0

    for snap in docs:
        if not snap.exists or snap.id == "info":
            continue
        data = snap.to_dict() or {}
        if data.get("agreeable_claims") or data.get("opposing_claims"):
            continue
        summary = (data.get("summary") or "").strip()
        if not summary:
            continue

        logger.info(f"[find_perspectives] {snap.id}: selecting agreeable/opposing")
        raw = _select_agreeable_opposing(summary, bank)
        a, o, reason = _parse_selection(raw)
        coll.document(snap.id).set(
            {"agreeable_claims": a, "opposing_claims": o, "claim_selection_reason": reason},
            merge=True,
        )
        updated += 1

    logger.info(f"[find_perspectives] updated={updated} event={event_id}")
    return updated




