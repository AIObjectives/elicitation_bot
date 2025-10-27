from typing import Iterable, Optional, List
from config.config import db, logger, client
from app.utils.validators import normalize_event_path

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
    coll = db.collection(normalize_event_path(event_id))

    docs = coll.stream() if not only_for else [coll.document(p).get() for p in only_for]
    batch = db.batch()
    updated = 0

    for i, snap in enumerate(docs):
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
        doc_ref = coll.document(snap.id)
        batch.set(doc_ref, {"summary": summary}, merge=True)
        updated += 1

        # Commit every 400–500 writes to stay under Firestore limit
        if updated % 400 == 0:
            batch.commit()
            batch = db.batch()


    if updated % 400 != 0:
        batch.commit()

    logger.info(f"[summarizer] updated={updated} event={event_id}")
    return updated
