import firebase_admin
from firebase_admin import credentials, firestore
import logging
from openai import OpenAI as _OpenAI

# === Config ===
OPENAI_API_KEY = "xxxx"  

client = _OpenAI(api_key=OPENAI_API_KEY)

# Initialize Firebase once
if not firebase_admin._apps:
    cred = credentials.Certificate('xxx')
    firebase_admin.initialize_app(cred)

db = firestore.client()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# === Step 1: Summarizer logic ===
def summarize_user_messages(messages):
    if not messages:
        return "No messages to summarize."

    system_message = (
        "You are a neutral assistant tasked with summarizing a user's perspective. "
        "Write a clear and concise summary in 1–2 sentences, keeping emotional tone, core themes, and clarity."
    )

    user_input = "Here are the user's messages:\n\n" + "\n".join(
        f"- {msg}" for msg in messages if msg
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input}
            ],
            max_tokens=300,
            temperature=0.2
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "⚠️ Error generating summary."


# === Step 2: Run summarization and store in Firestore ===
def summarize_and_store(event_id):
    collection_ref = db.collection(f"AOI_{event_id}")
    docs = collection_ref.stream()

    updated = 0
    for doc in docs:
        if doc.id == "info":
            continue

        data = doc.to_dict()
        interactions = data.get("interactions", [])
        messages = [x.get("message") for x in interactions if "message" in x]

        if not messages:
            continue

        logger.info(f"🔍 Summarizing user {doc.id} with {len(messages)} messages...")
        summary = summarize_user_messages(messages)

        # Update Firestore document with summary
        doc_ref = collection_ref.document(doc.id)
        doc_ref.update({"summary": summary})
        updated += 1
        logger.info(f"✅ Summary stored for {doc.id}")

    logger.info(f"🎉 Done. Stored {updated} user summaries for event: {event_id}")


# === Run directly ===
if __name__ == "__main__":
    EVENT_ID = "2ndroundtrial2"
    summarize_and_store(EVENT_ID)
