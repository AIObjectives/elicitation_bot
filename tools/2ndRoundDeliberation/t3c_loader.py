
import json
import hashlib
import uuid
from typing import List, Dict, Any, Optional
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# === CONFIG ===
SERVICE_ACCOUNT_JSON = "xxx.json" # Replace with your Firebase service account JSON path
COLLECTION_NAME = "xxx" # Replace with your desired collection name
FIRESTORE_DOC_HARD_LIMIT = 1_048_576
SAFETY_BYTES = 950_000  # Play it safe

# === FIREBASE INIT ===
def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_JSON)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# === HELPERS ===
def maybe_parse(x: Any) -> Any:
    if isinstance(x, str):
        s = x.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try: return json.loads(s)
            except Exception: return x
    return x

def walk_find_claim_blocks(node: Any) -> List[Any]:
    from collections import defaultdict
    found = defaultdict(list)
    def walk(n: Any):
        if isinstance(n, dict):
            for k, v in n.items():
                if k == "claims": found[k].append(v)
                walk(v)
        elif isinstance(n, list):
            for i in n: walk(i)
        elif isinstance(n, str):
            parsed = maybe_parse(n)
            if parsed is not n: walk(parsed)
    walk(node)
    return found["claims"]

def extract_title_text_pairs(claim_blocks: List[Any]) -> List[Dict[str, str]]:
    out = []
    seen = set()
    for block in claim_blocks:
        if isinstance(block, list):
            for c in block:
                if not isinstance(c, dict): continue
                title = c.get("title", "").strip()
                text = ""
                if isinstance(c.get("quotes"), list) and c["quotes"]:
                    first_quote = c["quotes"][0]
                    if isinstance(first_quote, dict):
                        text = first_quote.get("text", "").strip()
                key = f"{title}|{text}"
                if title and text and key not in seen:
                    out.append({
                        "claim_id": str(uuid.uuid4()),
                        "title": title,
                        "text": text
                    })
                    seen.add(key)
        elif isinstance(block, dict):
            title = block.get("title", "").strip()
            text = ""
            if isinstance(block.get("quotes"), list) and block["quotes"]:
                first_quote = block["quotes"][0]
                if isinstance(first_quote, dict):
                    text = first_quote.get("text", "").strip()
            key = f"{title}|{text}"
            if title and text and key not in seen:
                out.append({
                    "claim_id": str(uuid.uuid4()),
                    "title": title,
                    "text": text
                })
                seen.add(key)
    return out

def utf8_len(x: Any) -> int:
    return len(json.dumps(x, ensure_ascii=False).encode("utf-8"))

# === MAIN METADATA + CLAIM EXTRACTOR ===
def extract_metadata_and_claims(url: str) -> Dict[str, Any]:
    res = requests.get(url, timeout=30)
    res.raise_for_status()
    j = res.json()
    normalized = [maybe_parse(x) for x in j["data"]]

    entry = None
    for e in normalized:
        if isinstance(e, dict) and "title" in e:
            entry = e
            break
    if not entry:
        raise ValueError("No valid entry with title found.")

    metadata = {
        "title": entry.get("title"),
        "description": entry.get("description"),
        "date": entry.get("date"),
    }

    topics = entry.get("topics", [])
    overview = []
    total_subtopics = 0
    for t in topics:
        t_title = t.get("title")
        subtopics = t.get("subtopics", [])
        overview.append({
            "topic": t_title,
            "subtopic_count": len(subtopics)
        })
        total_subtopics += len(subtopics)
    metadata["total_topics"] = len(topics)
    metadata["total_subtopics"] = total_subtopics
    metadata["overview"] = overview

    sources = entry.get("sources", [])
    people = set()
    total_claims_est = 0
    for s in sources:
        if isinstance(s, str):
            try: s = json.loads(s)
            except: continue
        if isinstance(s, dict):
            person = s.get("interview") or s.get("name") or s.get("author")
            if person: people.add(person)
            total_claims_est += len(s.get("data", [])) if isinstance(s.get("data"), list) else 0
    metadata["total_people"] = len(people)
    metadata["total_claims"] = total_claims_est
    metadata["people_sample"] = list(people)[:5]

    claim_blocks = walk_find_claim_blocks(normalized)
    claims = extract_title_text_pairs(claim_blocks)
    metadata["claim_count_extracted"] = len(claims)

    return metadata, claims

# === STORAGE HANDLER ===
def store_in_chunks(metadata: Dict[str, Any], claims: List[Dict[str, str]], db=None):
    if db is None:
        db = init_firebase()

    base_doc_id = metadata["title"].replace(" ", "_")[:40] + "__" + hashlib.sha1(metadata["title"].encode()).hexdigest()[:8]
    chunks = []
    current_chunk = []
    current_size = utf8_len({"metadata": metadata, "claims": []})
    total_used = 0

    for claim in claims:
        claim_size = utf8_len(claim)
        if current_size + claim_size > SAFETY_BYTES:
            chunks.append(current_chunk)
            current_chunk = []
            current_size = utf8_len({"claims": []})  # metadata only goes in first doc
        current_chunk.append(claim)
        current_size += claim_size
    if current_chunk:
        chunks.append(current_chunk)

    print(f"📦 Total chunks to store: {len(chunks)}")
    for idx, chunk in enumerate(chunks):
        doc_id = f"{base_doc_id}__part{idx+1}"
        payload = {
            "claims": chunk
        }
        if idx == 0:
            payload["metadata"] = metadata

        size_bytes = utf8_len(payload)
        space_left = FIRESTORE_DOC_HARD_LIMIT - size_bytes
        print(f"📄 Chunk {idx+1}/{len(chunks)} → Claims: {len(chunk)} | Size: {size_bytes:,} bytes | Space left: {space_left:,} bytes")

        db.collection(COLLECTION_NAME).document(doc_id).set(payload)

    print("✅ All chunks successfully written to Firestore.")



if __name__ == "__main__":
    urls = [
        "https://...",
        "https://...",
        ...
    ]
    db = init_firebase()
    for url in urls:
        print(f"\n🚀 Processing: {url}")
        try:
            metadata, claims = extract_metadata_and_claims(url)
            store_in_chunks(metadata, claims, db=db)
        except Exception as e:
            print(f"❌ Error processing {url}: {e}")


# # === USAGE ===
# if __name__ == "__main__":
#     url ="XXX"  # Replace with your JSON URL
#     db = init_firebase()
#     metadata, claims = extract_metadata_and_claims(url)
#     store_in_chunks(metadata, claims, db=db)
