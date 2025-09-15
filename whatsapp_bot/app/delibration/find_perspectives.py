


# currently harcoded for test purposes - subject to change
import firebase_admin
from firebase_admin import credentials, firestore
import logging
from openai import OpenAI
import os

from openai import OpenAI as _OpenAI
# === 🔐 SETUP ===
OPENAI_API_KEY = "xxx"  

client = _OpenAI(api_key=OPENAI_API_KEY)

cred = credentials.Certificate('xxx.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EVENT_ID = "2ndroundtrial2"
COLLECTION_NAME = f"AOI_{EVENT_ID}"


# === 📁 Fetch claim source location ===
def get_claim_source_reference(event_id):
    if not event_id.startswith("AOI_"):
        event_id = f"AOI_{event_id}"

    info_ref = db.collection(event_id).document("info")
    info_doc = info_ref.get()

    if not info_doc.exists:
        raise Exception(f"No 'info' document found in event: {event_id}")

    info_data = info_doc.to_dict()
    source = info_data.get("second_round_claims_source", {})

    collection = source.get("collection")
    document = source.get("document")

    if not collection or not document:
        raise Exception("❌ Missing 'collection' or 'document' in second_round_claims_source")

    return collection, document


# === 📄 Fetch all claim texts ===
def fetch_all_claim_texts(collection_name, document_name):
    doc_ref = db.collection(collection_name).document(document_name)
    doc = doc_ref.get()

    if not doc.exists:
        raise Exception(f"Document '{document_name}' not found in collection '{collection_name}'")

    claims = doc.to_dict().get("claims", [])
    return [claim.get("text", "").strip() for claim in claims if claim.get("text")]


# === 🧠 Get user summary ===
# def get_user_summary(event_id, phone_number):
#     collection_name = f"AOI_{event_id}"
#     doc_ref = db.collection(collection_name).document(phone_number)
#     doc = doc_ref.get()

#     if not doc.exists():
#         return None

#     return doc.to_dict().get("summary")

def get_user_summary(event_id, phone_number):
    collection_name = f"AOI_{event_id}"
    doc_id = phone_number  # Already in 'whatsapp:+123...' format

    doc_ref = db.collection(collection_name).document(doc_id)
    doc = doc_ref.get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    return data.get("summary")



# === 🤖 Select claims + generate reason ===
def select_agreeable_opposing(summary, all_claim_texts):
    all_text_combined = "\n\n".join([f"[{i}] {text}" for i, text in enumerate(all_claim_texts)])

    system_prompt = (
        "You will be given a user summary and a list of claim texts.\n"
        "Pick 2 claims that strongly agree and 2 that strongly oppose the user's view.\n"
        "After that, include a one-sentence explanation of why you chose these claims.\n"
        "Respond in this format:\n\n"
        "**Agreeable Claims:**\n"
        "- [index] text\n"
        "- [index] text\n\n"
        "**Opposing Claims:**\n"
        "- [index] text\n"
        "- [index] text\n\n"
        "**Reason:** Your one sentence reason here."
    )

    user_prompt = f"User Summary:\n{summary.strip()}\n\nClaim Texts:\n{all_text_combined}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4,
            max_tokens=1200
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return None


# === 💾 Store to user doc directly ===
def store_results(event_id, phone_number, result):
    doc_ref = db.collection(event_id).document(phone_number)
    update_data = {}

    agreeable, opposing = [], []
    reason = None
    current_section = None

    for line in result.splitlines():
        line = line.strip()
        if line.startswith("**Agreeable"):
            current_section = "agreeable"
        elif line.startswith("**Opposing"):
            current_section = "opposing"
        elif line.startswith("**Reason:**"):
            reason = line.replace("**Reason:**", "").strip()
        elif line.startswith("- [") and "]" in line:
            if current_section == "agreeable":
                agreeable.append(line)
            elif current_section == "opposing":
                opposing.append(line)

    update_data["agreeable_claims"] = agreeable
    update_data["opposing_claims"] = opposing
    update_data["claim_selection_reason"] = reason or "No reason provided."

    doc_ref.set(update_data, merge=True)
    logger.info(f"✅ Stored claims + reason for {phone_number}")


# === 🚀 Run Main Loop ===
if __name__ == "__main__":
    try:
        collection_name, document_name = get_claim_source_reference(EVENT_ID)
        claim_texts = fetch_all_claim_texts(collection_name, document_name)

        collection_ref = db.collection(COLLECTION_NAME)
        docs = collection_ref.stream()
        total = 0

        for doc in docs:
            if doc.id == "info":
                continue

            phone_number = doc.id
            logger.info(f"📞 Processing user: {phone_number}")

            try:
                summary = get_user_summary(EVENT_ID, phone_number)
                if not summary:
                    logger.warning(f"⚠️ No summary found for {phone_number}")
                    continue
            except Exception as e:
                logger.warning(f"⚠️ Error retrieving summary for {phone_number}: {e}")
                continue

            result = select_agreeable_opposing(summary, claim_texts)
            if not result:
                logger.warning(f"⚠️ GPT failed for {phone_number}")
                continue

            store_results(COLLECTION_NAME, phone_number, result)
            total += 1

        logger.info(f"🎉 Finished processing {total} users for {EVENT_ID}")

    except Exception as err:
        logger.error(f"❌ Script failed: {err}")




