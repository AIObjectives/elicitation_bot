import firebase_admin
from firebase_admin import credentials, firestore
import logging
import os, json

FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON")

if not FIREBASE_CREDENTIALS_JSON:
    raise RuntimeError("Missing FIREBASE_CREDENTIALS_JSON environment variable")

cred = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS_JSON))
firebase_admin.initialize_app(cred)
db = firestore.client()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_blacklist_config(default_ttl_seconds=3600, initial_blocked_numbers=None):
    """
    Creates or updates everything under the same 'blocked_numbers' collection.
      - blocked_numbers/_config : stores cache TTL and other metadata
      - blocked_numbers/<phone_number> : empty doc or metadata for each blocked user
    """
    blk_ref = db.collection('blocked_numbers')

    # 1. Save the cache TTL under a special _config document
    config_ref = blk_ref.document('_config')
    config_ref.set({
        "cache_ttl_seconds": default_ttl_seconds
    }, merge=True)

    logger.info(f"[initialize_blacklist_config] Set cache_ttl_seconds={default_ttl_seconds}")

    # 2. Optionally preload blocked numbers
    if initial_blocked_numbers:
        for num in initial_blocked_numbers:
            blk_ref.document(num).set({})  # Empty doc = blocked
            logger.info(f"[initialize_blacklist_config] Added blocked number: {num}")

if __name__ == "__main__":
    initialize_blacklist_config(
        default_ttl_seconds=3600,  # 1-hour cache TTL
        initial_blocked_numbers=[
            "+whatsapp:131xxx",
            "+whatsapp:131xxx",
            "whatsapp:"  # add more as needed
        ]
    )

    # Optional verification
    doc = db.collection("blocked_numbers").document("_config").get()
    print("Config exists:", doc.exists)
    if doc.exists:
        print("Data:", doc.to_dict())
    else:
        print("⚠️ Still missing – check credentials or Firestore project ID.")
