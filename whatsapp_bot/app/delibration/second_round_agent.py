




# currently hardcoded - subject to change
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from firebase_admin import firestore
from openai import OpenAI

db = firestore.client()
client = OpenAI()
logger = logging.getLogger(__name__)

# -----------------------------
# Fetch report / metadata once
# -----------------------------
def fetch_report_metadata(event_id: str) -> Dict[str, Any]:
    event_path = event_id if event_id.startswith("AOI_") else f"AOI_{event_id}"
    info_ref = db.collection(event_path).document("info")
    info_doc = info_ref.get()
    if not info_doc.exists:
        return {}
    src = (info_doc.to_dict() or {}).get("second_round_claims_source", {}) or {}
    collection = src.get("collection")
    document = src.get("document")
    if not collection or not document:
        return {}
    rep = db.collection(collection).document(document).get()
    return (rep.to_dict() or {}).get("metadata", {}) if rep.exists else {}

# ---------------------------------------
# Pull user context + last turns to ground
# ---------------------------------------
def get_user_context(
    event_id: str,
    phone_number: str,
    history_k: int = 6,
) -> Optional[Tuple[str, List[str], List[str], Optional[str], List[Dict[str, str]], bool]]:
    """
    Returns:
      summary, agreeable, opposing, claim_selection_reason, recent_turns, intro_done
    recent_turns: list of {'role': 'user'|'assistant', 'text': str}
    """
    event_path = event_id if event_id.startswith("AOI_") else f"AOI_{event_id}"
    user_ref = db.collection(event_path).document(phone_number)
    snap = user_ref.get()
    if not snap.exists:
        return None

    data = snap.to_dict() or {}
    summary   = data.get("summary")
    agreeable = data.get("agreeable_claims", []) or []
    opposing  = data.get("opposing_claims", []) or []
    reason    = data.get("claim_selection_reason")
    intro_done = bool(data.get("second_round_intro_done", False))

    # Build lightweight recent turns from 'second_round_interactions'
    raw = data.get("second_round_interactions", []) or []
    turns: List[Dict[str, str]] = []
    for item in raw:
        if "message" in item:
            turns.append({"role": "user", "text": str(item["message"])})
        elif "response" in item:
            turns.append({"role": "assistant", "text": str(item["response"])})

    turns = turns[-history_k:]

    if not summary or (not agreeable and not opposing):
        return None
    return summary, agreeable, opposing, reason, turns, intro_done

# ---------------------------------------
# Compose a prompt that is *stateful* + brief
# ---------------------------------------
def build_second_round_message(
    user_msg: str,
    summary: str,
    agreeable: List[str],
    opposing: List[str],
    metadata: Dict[str, Any],
    claim_selection_reason: Optional[str],
    recent_turns: List[Dict[str, str]],
    intro_done: bool,
) -> Optional[str]:

    # Ground with short history
    history_block = ""
    if recent_turns:
        parts = []
        for t in recent_turns:
            role = "User" if t["role"] == "user" else "Assistant"
            snippet = " ".join(t["text"].split())  # squash whitespace
            if len(snippet) > 220:
                snippet = snippet[:220] + "…"
            parts.append(f"{role}: {snippet}")
        history_block = "Recent Dialogue (latest last):\n" + "\n".join(parts) + "\n\n"

    # Only show claims on first turn unless asked
    if intro_done:
        agree_block  = "(hidden—show only if user asks)"
        oppose_block = "(hidden—show only if user asks)"
    else:
        agree_block  = "\n".join(agreeable[:2]) if agreeable else "(none)"
        oppose_block = "\n".join(opposing[:2])  if opposing  else "(none)"

    reason_line = f"\nClaim selection note: {claim_selection_reason}" if (claim_selection_reason and not intro_done) else ""

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
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[2nd-round] GPT error: {e}")
        return None

# ---------------------------------------
# Public entry used by your message handler
# ---------------------------------------
def run_second_round_for_user(
    event_id: str,
    phone_number: str,
    user_msg: Optional[str] = None
) -> Optional[str]:
    """Return the agent's brief, context-aware reply."""
    if not user_msg:
        user_msg = ""

    metadata = fetch_report_metadata(event_id)
    ctx = get_user_context(event_id, phone_number)
    if not ctx:
        return None

    summary, agreeable, opposing, reason, recent_turns, intro_done = ctx

    reply = build_second_round_message(
        user_msg=user_msg,
        summary=summary,
        agreeable=agreeable,
        opposing=opposing,
        metadata=metadata,
        claim_selection_reason=reason,
        recent_turns=recent_turns,
        intro_done=intro_done,
    )
    if not reply:
        return None

    # Mark intro done after first successful response
    if not intro_done:
        event_path = event_id if event_id.startswith("AOI_") else f"AOI_{event_id}"
        db.collection(event_path).document(phone_number).set(
            {"second_round_intro_done": True}, merge=True
        )

    return reply
