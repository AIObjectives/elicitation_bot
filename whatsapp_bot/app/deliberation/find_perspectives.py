from typing import Iterable, Optional, List
from config.config import logger, client
from app.services.firestore_service import ReportService

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
    col, doc = ReportService.get_claim_source_reference(event_id)
    bank = ReportService.fetch_all_claim_texts(col, doc)
    if not bank:
        logger.warning(f"[find_perspectives] empty claim bank {col}/{doc}")
        return 0

    updated = 0

    for snap in ReportService.stream_event_participants(event_id, list(only_for) if only_for else None):
        if snap.id == "info":
            continue

        if ReportService.has_perspective_claims(event_id, snap.id):
            continue

        summary = ReportService.get_participant_summary(event_id, snap.id)
        if not summary:
            continue

        logger.info(f"[find_perspectives] {snap.id}: selecting agreeable/opposing")
        raw = _select_agreeable_opposing(summary, bank)
        a, o, reason = _parse_selection(raw)
        ReportService.set_perspective_claims(event_id, snap.id, a, o, reason)
        updated += 1

    logger.info(f"[find_perspectives] updated={updated} event={event_id}")
    return updated




