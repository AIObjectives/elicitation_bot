import os
import json
import hashlib
import uuid
import requests
import streamlit as st
from typing import Any, Dict, List, Tuple
from google.cloud import storage
from google.oauth2 import service_account
import firebase_admin
from firebase_admin import credentials, firestore

# ====================================================
# ENVIRONMENT VARIABLES (set in Heroku dashboard)
# ====================================================
FIREBASE_SA_JSON = os.environ.get("FIREBASE_SA_JSON")  # full JSON string
GCS_SA_JSON = os.environ.get("GCS_SA_JSON")            # full JSON string
DEFAULT_COLLECTION_NAME = os.environ.get("DEFAULT_COLLECTION_NAME", "t3cloaderapp")
DEFAULT_BUCKET_NAME = os.environ.get("DEFAULT_BUCKET_NAME", "tttc-light-newbucket")

FIRESTORE_DOC_HARD_LIMIT = 1_048_576
SAFETY_BYTES = 950_000

# ====================================================
# FIREBASE INIT
# ====================================================
def init_firebase():
    if not firebase_admin._apps:
        if not FIREBASE_SA_JSON:
            raise RuntimeError("Missing FIREBASE_SA_JSON env var")
        cred_dict = json.loads(FIREBASE_SA_JSON)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# ====================================================
# AUTH HELPERS
# ====================================================
def _hash_pw(pw: str) -> str:
    return hashlib.sha256((pw or "").encode()).hexdigest()


def validate_user(username: str, password: str) -> bool:
    """Check Firestore users collection for matching username + password hash."""
    try:
        doc_ref = db.collection("2nd_round_users").document(username)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        user_data = doc.to_dict() or {}
        stored_pw = user_data.get("password_hash") 
        return stored_pw == password 
    except Exception as e:
        st.error(f"Auth error: {e}")
        return False

def require_login() -> bool:
    if "authed" not in st.session_state:
        st.session_state["authed"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None

    st.markdown("## 🔐 Login")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            if validate_user(username.strip(), password.strip()):
                st.session_state["authed"] = True
                st.session_state["username"] = username
            else:
                st.error("Invalid username or password.")
    return st.session_state["authed"]

def logout_button():
    if st.session_state.get("authed"):
        if st.button("Logout"):
            st.session_state["authed"] = False
            st.session_state["username"] = None
            st.rerun()

# ====================================================
# HELPERS (claims + GCS)
# ====================================================
def utf8_len(x: Any) -> int:
    return len(json.dumps(x, ensure_ascii=False).encode("utf-8"))

def maybe_parse(x: Any) -> Any:
    if isinstance(x, str):
        s = x.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                return json.loads(s)
            except Exception:
                return x
    return x

def walk_find_claim_blocks(node: Any) -> List[Any]:
    from collections import defaultdict
    found = defaultdict(list)
    def walk(n: Any):
        if isinstance(n, dict):
            for k, v in n.items():
                if k == "claims":
                    found[k].append(v)
                walk(v)
        elif isinstance(n, list):
            for i in n: walk(i)
        elif isinstance(n, str):
            parsed = maybe_parse(n)
            if parsed is not n: walk(parsed)
    walk(node)
    return found["claims"]

def extract_title_text_pairs(claim_blocks: List[Any]) -> List[Dict[str, str]]:
    out, seen = [], set()
    def take_title_text(c: Dict[str, Any]) -> Tuple[str, str]:
        title = (c.get("title") or "").strip()
        text = ""
        quotes = c.get("quotes")
        if isinstance(quotes, list) and quotes:
            first_quote = quotes[0]
            if isinstance(first_quote, dict):
                text = (first_quote.get("text") or "").strip()
        return title, text
    for block in claim_blocks:
        if isinstance(block, list):
            for c in block:
                if not isinstance(c, dict): continue
                title, text = take_title_text(c)
                key = f"{title}|{text}"
                if title and text and key not in seen:
                    out.append({"claim_id": str(uuid.uuid4()), "title": title, "text": text})
                    seen.add(key)
        elif isinstance(block, dict):
            title, text = take_title_text(block)
            key = f"{title}|{text}"
            if title and text and key not in seen:
                out.append({"claim_id": str(uuid.uuid4()), "title": title, "text": text})
                seen.add(key)
    return out

# ====================================================
# GCS SIGNED URL GENERATOR
# ====================================================
def generate_signed_url(bucket_name: str, blob_name: str, expiration: int = 3600) -> str:
    if not GCS_SA_JSON:
        raise RuntimeError("Missing GCS_SA_JSON env var")
    creds_dict = json.loads(GCS_SA_JSON)
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    client = storage.Client(credentials=creds)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.generate_signed_url(version="v4", expiration=expiration, method="GET")

# ====================================================
# METADATA EXTRACTION
# ====================================================

def extract_metadata_and_claims(url: str) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    res = requests.get(url, timeout=30)
    res.raise_for_status()
    j = res.json()
    if not isinstance(j, dict) or "data" not in j or not isinstance(j["data"], list):
        raise ValueError("Unexpected JSON format: missing 'data'.")
    normalized = [maybe_parse(x) for x in j["data"]]
    entry = next((e for e in normalized if isinstance(e, dict) and "title" in e), None)
    if not entry:
        raise ValueError("No valid entry with 'title' found.")
    metadata: Dict[str, Any] = {
        "title": entry.get("title"),
        "description": entry.get("description"),
        "date": entry.get("date"),
    }
    topics = entry.get("topics", [])
    overview, total_subtopics = [], 0
    if isinstance(topics, list):
        for t in topics:
            if not isinstance(t, dict): continue
            t_title = t.get("title")
            subs = t.get("subtopics", [])
            overview.append({"topic": t_title, "subtopic_count": len(subs) if isinstance(subs, list) else 0})
            total_subtopics += len(subs) if isinstance(subs, list) else 0
    metadata["total_topics"] = len(topics) if isinstance(topics, list) else 0
    metadata["total_subtopics"] = total_subtopics
    metadata["overview"] = overview
    sources = entry.get("sources", [])
    people, total_claims_est = set(), 0
    if isinstance(sources, list):
        for s in sources:
            if isinstance(s, str):
                try: s = json.loads(s)
                except: continue
            if isinstance(s, dict):
                person = s.get("interview") or s.get("name") or s.get("author")
                if person: people.add(person)
                data = s.get("data")
                if isinstance(data, list): total_claims_est += len(data)
    metadata["total_people"] = len(people)
    metadata["total_claims"] = total_claims_est
    #metadata["people_sample"] = list(people)[:5]
    claim_blocks = walk_find_claim_blocks(normalized)
    claims = extract_title_text_pairs(claim_blocks)
    metadata["claim_count_extracted"] = len(claims)
    return metadata, claims

# ====================================================
# FIRESTORE STORAGE
# ====================================================
def store_in_chunks_with_progress(collection_name: str, metadata: Dict[str, Any], claims: List[Dict[str, str]], db=None):
    if db is None: raise ValueError("Firestore client required")
    title = (metadata.get("title") or "untitled").strip()
    MAX_TITLE_LENGTH = 100  # or 400
    safe_title = title.replace(" ", "_")[:MAX_TITLE_LENGTH] or "untitled"
    base_doc_id = f"{safe_title}__{hashlib.sha1(title.encode()).hexdigest()[:8]}"
    chunks, current_chunk, current_size = [], [], utf8_len({"metadata": metadata, "claims": []})
    for claim in claims:
        claim_size = utf8_len(claim)
        if current_size + claim_size > SAFETY_BYTES:
            chunks.append(current_chunk)
            current_chunk, current_size = [], utf8_len({"claims": []})
        current_chunk.append(claim)
        current_size += claim_size
    if current_chunk: chunks.append(current_chunk)

    report, progress = [], st.progress(0, text="Writing to Firestore...")
    total = len(chunks)
    for idx, chunk in enumerate(chunks):
        doc_id = f"{base_doc_id}__part{idx+1}"
        payload = {"claims": chunk}
        if idx == 0: payload["metadata"] = metadata
        size_bytes = utf8_len(payload)
        space_left = FIRESTORE_DOC_HARD_LIMIT - size_bytes
        db.collection(collection_name).document(doc_id).set(payload)
        report.append({
            "doc_id": doc_id, 
            "claims_in_chunk": len(chunk),
            "size_bytes": size_bytes,
            "space_left": space_left
        })
        progress.progress(int(((idx+1)/total)*100), text=f"Writing chunk {idx+1}/{total}…")
        st.write(f"✅ Wrote chunk {idx+1}/{total}: {len(chunk)} claims, {size_bytes:,} bytes (space left: {space_left:,} bytes)")
    progress.empty()
    return report

# ====================================================
# STREAMLIT UI
# ====================================================
st.set_page_config(page_title="Second-Round Ingest → Firestore", page_icon="🧩", layout="centered")

if not require_login(): st.stop()
st.title(f"🧩 Second-Round Ingest → Firestore (Welcome {st.session_state['username']})")
logout_button()

with st.expander("Configuration", expanded=False):
    collection_name = st.text_input("Firestore collection name:", value=DEFAULT_COLLECTION_NAME)

st.markdown("### 📂 GCS File Selection")
bucket_name = st.text_input("Bucket name", value=DEFAULT_BUCKET_NAME)
blob_name = st.text_input("File name (e.g. ai_assembly_2023_t3c.json)", value="")
expiration_seconds = st.number_input(
    "Signed URL expiration time (in seconds)", 
    min_value=60, max_value=604800, value=3600, step=60
)

signed_url = ""
if bucket_name and blob_name:
    try:
        signed_url = generate_signed_url(bucket_name, blob_name, expiration=expiration_seconds)
        st.success(f"Signed URL generated successfully (valid for {expiration_seconds} seconds). Click Preview to fetch JSON.")
        st.text_area("Signed URL (auto-generated)", value=signed_url, height=80)
    except Exception as e:
        st.error(f"Error generating signed URL: {e}")

preview_btn = st.button("🔍 Preview JSON")
write_btn = st.button("📝 Write to Firestore")
if "previews" not in st.session_state: st.session_state["previews"] = {}

if preview_btn and signed_url:
    try:
        metadata, claims = extract_metadata_and_claims(signed_url)
        st.session_state["previews"][signed_url] = {"ok": True, "metadata": metadata, "claims": claims}
        st.success(f"Preview success: {len(claims)} claims extracted")
        st.json(metadata)
    except Exception as e:
        st.session_state["previews"][signed_url] = {"ok": False, "error": str(e)}
        st.error(f"Error previewing JSON: {e}")

if write_btn:
    if not st.session_state["previews"]:
        st.error("Nothing to write. Preview first.")
    else:
        try:
            db = init_firebase()
            for url, p in st.session_state["previews"].items():
                if not p.get("ok"): continue
                report = store_in_chunks_with_progress(collection_name.strip(), p["metadata"], p["claims"], db=db)
                st.success(f"Stored {len(p['claims'])} claims into '{collection_name}'")
                with st.expander("Firestore Write Details"):
                    for item in report:
                        st.write(f"- {item['doc_id']} — {item['claims_in_chunk']} claims, {item['size_bytes']:,} bytes (space left: {item['space_left']:,} bytes)")
        except Exception as e:
            st.error(f"Error writing to Firestore: {e}")
