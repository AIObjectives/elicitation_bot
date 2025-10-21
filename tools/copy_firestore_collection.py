import firebase_admin
from firebase_admin import credentials, firestore
import os, json

FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON")

if not FIREBASE_CREDENTIALS_JSON:
    raise RuntimeError("Missing FIREBASE_CREDENTIALS_JSON environment variable")

cred = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS_JSON))
firebase_admin.initialize_app(cred)
db = firestore.client()

def copy_collection(source_collection_ref, target_collection_ref):
    """ Copy all documents and subcollections from source to target collection """
    docs = source_collection_ref.stream()
    for doc in docs:
        # Copy document data to the target collection
        target_doc_ref = target_collection_ref.document(doc.id)
        target_doc_ref.set(doc.to_dict())

        # Copy subcollections recursively
        for subcollection in doc.reference.collections():
            copy_subcollection(subcollection, target_doc_ref.collection(subcollection.id))

def copy_subcollection(source_subcollection_ref, target_subcollection_ref):
    """ Recursively copy subcollections """
    docs = source_subcollection_ref.stream()
    for doc in docs:
        # Copy document data to the target subcollection
        target_doc_ref = target_subcollection_ref.document(doc.id)
        target_doc_ref.set(doc.to_dict())

        # Recursively copy nested subcollections
        for nested_subcollection in doc.reference.collections():
            copy_subcollection(nested_subcollection, target_doc_ref.collection(nested_subcollection.id))

# Define source and target collection names
source_collection_name = 'xxx'
target_collection_name = 'xxx'  

# Get references to the source and target collections
source_collection_ref = db.collection(source_collection_name)
target_collection_ref = db.collection(target_collection_name)

# Copy the collection
print(f"Copying collection '{source_collection_name}' to '{target_collection_name}'")
copy_collection(source_collection_ref, target_collection_ref)
print(f"Collection '{source_collection_name}' successfully copied to '{target_collection_name}'")