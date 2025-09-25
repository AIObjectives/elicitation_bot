from typing import Iterable, Optional, List
from config.config import db, logger, client

def _summarize_user_messages(messages: List[str]) -> str:
    if not messages:
        return "No messages to summarize."
    system_message = (
        "You are a neutral assistant tasked with summarizing a user's perspective. "
        "Write a clear and concise summary in 1–2 sentences, preserving tone and core themes."
    )
    user_input = "Here are the user's messages:\n\n" + "\n".join(f"- {m}" for m in messages if m)

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input},
            ],
            max_tokens=300,
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip() or "Summary unavailable."
    except Exception as e:
        logger.error(f"[summarizer] OpenAI error: {e}")
        return "⚠️ Error generating summary."

def summarize_and_store(event_id: str, only_for: Optional[Iterable[str]] = None) -> int:
    """Create 'summary' for users that don't have one yet. Safe/idempotent."""
    coll = db.collection(f"AOI_{event_id}")
    docs = coll.stream() if not only_for else [coll.document(p).get() for p in only_for]
    updated = 0

    for snap in docs:
        if not snap.exists or snap.id == "info":
            continue
        data = snap.to_dict() or {}
        if (data.get("summary") or "").strip():
            continue

        interactions = data.get("interactions", []) or []
        msgs = [x.get("message") for x in interactions if isinstance(x, dict) and x.get("message")]
        if not msgs:
            continue

        logger.info(f"[summarizer] {snap.id}: {len(msgs)} msgs → summary")
        summary = _summarize_user_messages(msgs)
        coll.document(snap.id).set({"summary": summary}, merge=True)
        updated += 1

    logger.info(f"[summarizer] updated={updated} event={event_id}")
    return updated
