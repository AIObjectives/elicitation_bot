import os
import json
import hashlib
import uuid
from typing import List, Dict, Any, Tuple

import requests
import streamlit as st

import firebase_admin
from firebase_admin import credentials, firestore


# Hard-coded password for testing
os.environ["STREAMLIT_APP_PASSWORD"] = "xxx"


# =========================================
# Authentication (password gate)
# =========================================
def _derive_hash_from_plaintext(pw: str) -> str:
    return hashlib.sha256((pw or "").encode()).hexdigest()

def _load_expected_pw_hash() -> str:
    pw_hash = os.environ.get("STREAMLIT_APP_PASSWORD_HASH", "").strip()
    if pw_hash:
        return pw_hash
    pw_plain = os.environ.get("STREAMLIT_APP_PASSWORD", "").strip()
    if pw_plain:
        return _derive_hash_from_plaintext(pw_plain)
    return ""

def require_password() -> bool:
    if "authed" not in st.session_state:
        st.session_state["authed"] = False
    expected_hash = _load_expected_pw_hash()
    st.markdown("## 🔐 Login")
    if not expected_hash:
        st.error("No password configured. Set STREAMLIT_APP_PASSWORD or STREAMLIT_APP_PASSWORD_HASH.")
        return False
    with st.form("login_form", clear_on_submit=False):
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            if _derive_hash_from_plaintext(pw) == expected_hash:
                st.session_state["authed"] = True
            else:
                st.error("Incorrect password.")
    return st.session_state["authed"]

def logout_button():
    if st.session_state.get("authed"):
        if st.button("Logout"):
            st.session_state["authed"] = False
            st.rerun()


# =========================================
# Config
# =========================================
DEFAULT_SERVICE_ACCOUNT_JSON = "xxx"
DEFAULT_COLLECTION_NAME = "t3cloaderapp"
DEFAULT_GCS_BUCKET_PREFIX = "https://storage.googleapis.com/your-bucket/"
FIRESTORE_DOC_HARD_LIMIT = 1_048_576
SAFETY_BYTES = 950_000


# =========================================
# Firebase init
# =========================================
def init_firebase(service_account_json: str):
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_json)
        firebase_admin.initialize_app(cred)
    return firestore.client()


# =========================================
# Helpers
# =========================================
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
            for i in n:
                walk(i)
        elif isinstance(n, str):
            parsed = maybe_parse(n)
            if parsed is not n:
                walk(parsed)
    walk(node)
    return found["claims"]

def extract_title_text_pairs(claim_blocks: List[Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
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

def utf8_len(x: Any) -> int:
    return len(json.dumps(x, ensure_ascii=False).encode("utf-8"))

def build_url_from_input(raw: str, default_bucket_prefix: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if not default_bucket_prefix.endswith("/"):
        default_bucket_prefix += "/"
    if not s.endswith(".json"):
        s += ".json"
    return default_bucket_prefix + s


# =========================================
# Extract metadata + claims
# =========================================
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
    metadata["people_sample"] = list(people)[:5]
    claim_blocks = walk_find_claim_blocks(normalized)
    claims = extract_title_text_pairs(claim_blocks)
    metadata["claim_count_extracted"] = len(claims)
    return metadata, claims


# =========================================
# Firestore storage with progress
# =========================================
def store_in_chunks_with_progress(collection_name: str, metadata: Dict[str, Any], claims: List[Dict[str, str]], db=None):
    if db is None: raise ValueError("Firestore client required")
    title = (metadata.get("title") or "untitled").strip()
    safe_title = title.replace(" ", "_")[:40] or "untitled"
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
    report = []
    progress = st.progress(0, text="Writing to Firestore...")
    total = len(chunks)
    for idx, chunk in enumerate(chunks):
        doc_id = f"{base_doc_id}__part{idx+1}"
        payload = {"claims": chunk}
        if idx == 0: payload["metadata"] = metadata
        size_bytes = utf8_len(payload)
        space_left = FIRESTORE_DOC_HARD_LIMIT - size_bytes
        db.collection(collection_name).document(doc_id).set(payload)
        report.append({"doc_id": doc_id, "claims_in_chunk": len(chunk), "size_bytes": size_bytes, "space_left": space_left})
        progress.progress(int(((idx+1)/total)*100), text=f"Writing chunk {idx+1}/{total}…")
        st.write(f"✅ Wrote chunk {idx+1}/{total}: {len(chunk)} claims, {size_bytes:,} bytes")
    progress.empty()
    return report


# =========================================
# Streamlit UI
# =========================================
st.set_page_config(page_title="Second-Round Ingest → Firestore", page_icon="🧩", layout="centered")
if not require_password(): st.stop()
st.title("🧩 Second-Round Deliberation Ingest → Firestore")
logout_button()

with st.expander("Firebase configuration", expanded=False):
    service_account_json = st.text_input("Service account JSON path:", value=DEFAULT_SERVICE_ACCOUNT_JSON, type="password")
    collection_name = st.text_input("Firestore collection name:", value=DEFAULT_COLLECTION_NAME)
    default_bucket_prefix = st.text_input("Default bucket prefix:", value=DEFAULT_GCS_BUCKET_PREFIX)
urls_or_ids = st.text_area("Report URLs or IDs (one per line)", height=120)
preview_btn = st.button("🔍 Preview")
write_btn = st.button("📝 Write to Firestore")
if "previews" not in st.session_state: st.session_state["previews"] = {}

def do_preview():
    st.session_state["previews"].clear()
    resolved = [build_url_from_input(x.strip(), default_bucket_prefix) for x in urls_or_ids.splitlines() if x.strip()]
    for u in resolved:
        try:
            metadata, claims = extract_metadata_and_claims(u)
            st.session_state["previews"][u] = {"ok": True, "url": u, "metadata": metadata, "claims": claims, "claim_count": len(claims)}
            st.success(f"Previewed {u}: {len(claims)} claims")
        except Exception as e:
            st.session_state["previews"][u] = {"ok": False, "url": u, "error": str(e)}
            st.error(f"Error previewing {u}: {e}")

def do_write():
    if not st.session_state["previews"]:
        st.error("Nothing to write. Preview first.")
        return
    try: db = init_firebase(service_account_json)
    except Exception as e:
        st.error(f"Firebase init error: {e}"); return
    for u, p in st.session_state["previews"].items():
        if not p.get("ok"): continue
        try:
            report = store_in_chunks_with_progress(collection_name.strip(), p["metadata"], p["claims"], db=db)
            st.success(f"Stored {p['claim_count']} claims from {u} into '{collection_name}'")
            with st.expander(f"Details for {u}"):
                for item in report:
                    st.write(f"- {item['doc_id']} — {item['claims_in_chunk']} claims, {item['size_bytes']:,} bytes")
        except Exception as e:
            st.error(f"Write error for {u}: {e}")

if preview_btn: do_preview()
if write_btn: do_write()
