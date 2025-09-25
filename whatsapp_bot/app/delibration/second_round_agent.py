from typing import Dict, Any, List, Optional, Tuple
from config.config import db, logger, client
from app.delibration.summarizer import summarize_and_store
from app.delibration.find_perspectives import select_and_store_for_event

# ---------- helpers ----------
def _fetch_report_metadata(event_id: str) -> Dict[str, Any]:
    path = f"AOI_{event_id}" if not event_id.startswith("AOI_") else event_id
    info = db.collection(path).document("info").get()
    if not info.exists:
        return {}
    src = (info.to_dict() or {}).get("second_round_claims_source", {}) or {}
    col, doc = src.get("collection"), src.get("document")
    if not col or not doc:
        return {}
    rep = db.collection(col).document(doc).get()
    return (rep.to_dict() or {}).get("metadata", {}) if rep.exists else {}

def _get_user_context(event_id: str, phone: str, history_k: int = 6):
    path = f"AOI_{event_id}" if not event_id.startswith("AOI_") else event_id
    snap = db.collection(path).document(phone).get()
    if not snap.exists:
        return None
    d = snap.to_dict() or {}
    summary   = d.get("summary")
    agreeable = d.get("agreeable_claims", []) or []
    opposing  = d.get("opposing_claims", []) or []
    reason    = d.get("claim_selection_reason")
    intro_done= bool(d.get("second_round_intro_done", False))
    raw = d.get("second_round_interactions", []) or []
    turns = []
    for it in raw:
        if "message" in it:    turns.append({"role": "user", "text": str(it["message"])})
        elif "response" in it: turns.append({"role": "assistant", "text": str(it["response"])})
    return summary, agreeable, opposing, reason, turns[-history_k:], intro_done

def _build_reply(user_msg, summary, agreeable, opposing, metadata, reason, recent_turns, intro_done) -> Optional[str]:
    history_block = ""
    if recent_turns:
        parts = []
        for t in recent_turns:
            role = "User" if t["role"] == "user" else "Assistant"
            snippet = " ".join(t["text"].split())
            if len(snippet) > 220:
                snippet = snippet[:220] + "…"
            parts.append(f"{role}: {snippet}")
        history_block = "Recent Dialogue (latest last):\n" + "\n".join(parts) + "\n\n"

    agree_block, oppose_block = "(none)", "(none)"
    if intro_done:
        agree_block = "(hidden—show only if user asks)"
        oppose_block = "(hidden—show only if user asks)"
    else:
        if agreeable: agree_block = "\n".join(agreeable[:2])
        if opposing:  oppose_block = "\n".join(opposing[:2])

    reason_line = f"\nClaim selection note: {reason}" if (reason and not intro_done) else ""

    system_prompt = (
        "You are a concise, context-aware *second-round deliberation* assistant.\n"
        "Goals: keep flow natural, avoid repetition, and deepen the user's thinking with concrete contrasts.\n"
        "Hard rules:\n"
        "- NEVER re-introduce the whole setup after the intro.\n"
        "- Keep replies short: 1–4 crisp sentences, <= ~400 characters total.\n"
        "- Answer the user's exact question first; then, if helpful, add ONE brief nudge.\n"
        "- Do not ask generic questions like 'What aspect...?'—be specific and grounded.\n"
        "- Only restate claims if the user asks for them.\n"
    )

    user_prompt = (
        f"{history_block}"
        f"User Summary: {summary}\n"
        f"Report Metadata (context only): {metadata}\n"
        f"Agreeable (grounding): {agree_block}\n"
        f"Opposing (grounding): {oppose_block}"
        f"{reason_line}\n\n"
        f"Current user message: {user_msg}\n\n"
        "Respond now following the rules above. If the user asks 'what are we doing', reply with ONE sentence and pivot to a pointed follow-up.\n"
        "If the user asks whether you can access others' reports, answer briefly: you have curated claims (not direct personal data), then offer a one-line, targeted next step.\n"
        "When relevant, introduce another participant’s claim naturally, e.g., 'Here’s something that aligns with your view—do you agree?' or 'Here’s an opposing view—how would you respond?'\n"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
            max_tokens=200,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"[2nd-round] GPT error: {e}")
        return None

# ---------- public entry ----------
def run_second_round_for_user(event_id: str, phone_number: str, user_msg: Optional[str] = "") -> Optional[str]:
    """
    If the user lacks summary or claim selections, this will:
      1) summarize_and_store(event_id, only_for=[phone_number])
      2) select_and_store_for_event(event_id, only_for=[phone_number])
    Then it retries once to build the reply.
    """
    def _attempt(after_warm: bool = False) -> Optional[str]:
        meta = _fetch_report_metadata(event_id)
        ctx = _get_user_context(event_id, phone_number)
        if not ctx:
            return None
        summary, agreeable, opposing, reason, turns, intro_done = ctx
        if not summary or (not agreeable and not opposing):
            if after_warm:
                return None
            # warm just this user
            summarize_and_store(event_id, only_for=[phone_number])
            select_and_store_for_event(event_id, only_for=[phone_number])
            return _attempt(after_warm=True)
        return _build_reply(user_msg, summary, agreeable, opposing, meta, reason, turns, intro_done)

    reply = _attempt()
    if reply is None:
        return None

    # mark intro finished after a successful turn
    path = f"AOI_{event_id}" if not event_id.startswith("AOI_") else event_id
    db.collection(path).document(phone_number).set({"second_round_intro_done": True}, merge=True)
    return reply
