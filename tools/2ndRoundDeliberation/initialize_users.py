import hashlib
import firebase_admin
from firebase_admin import credentials, firestore
import os, json

FIREBASE_SA = "xxx"

def _hash_pw(pw: str) -> str:
    return hashlib.sha256((pw or "").encode()).hexdigest()

def init_users():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_SA)
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    users_ref = db.collection("2nd_round_users")
    
    users_ref.document("xxx").set({
        "username": "xxx",
        #"password_hash": _hash_pw("xx")
        "password_hash": "xx"
        
    })

    users_ref.document("bob").set({
        "username": "bob",
        "password_hash": _hash_pw("bobpass")
        

    })

    print("✅ Users initialized.")

if __name__ == "__main__":
    init_users()
