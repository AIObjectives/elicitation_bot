````markdown
# 🧩 Second-Round Deliberation Ingest → Firestore

This project provides a **Streamlit web application** for ingesting structured JSON data stored in **Google Cloud Storage (GCS)** into **Google Firestore**.  
It was designed to support large-scale deliberation datasets, while handling Firestore’s **1MB document size limit** through intelligent chunking.

---


---

## 🏗️ Architecture

The app integrates four main components:

1. **Authentication Layer**
   - Firebase Auth

2. **Google Cloud Storage**
   - Uses service account credentials to generate **signed URLs**.
   - Files are fetched in real time via signed links.

3. **Metadata + Claims Extraction**
   - Parses the JSON structure to extract:
     - Report metadata (title, description, date, topics, people, etc.)
     - Normalized claims with unique IDs.
   - Handles nested structures and JSON-in-string values with a `maybe_parse` helper.

4. **Firestore Ingestion**
   - Writes claims in chunks to Firestore.
   - Ensures each document remains under the 1MB hard limit.
   - Automatically appends `__partN` suffix for chunked documents.

---

## 🖥️ Running Locally

1. Clone the repo:

   ```bash
   git clone https://github.com/<your-repo>.git
   cd <your-repo>
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:

   ```bash
   streamlit run app.py
   ```

---

## ☁️ Deploying to Heroku

1. Login:

   ```bash
   heroku login
   ```

2. Create app:

   ```bash
   heroku create your-app-name
   ```

3. Add buildpacks:

   ```bash
   heroku buildpacks:add heroku/python
   ```

4. Set config vars (example for JSON keys):

   ```bash
   heroku config:set FIRESTORE_SA_JSON="$(base64 -i path/to/firebase.json)"
   heroku config:set GCS_SA_JSON="$(base64 -i path/to/gcs.json)"
   ```

5. Push to Heroku:

   ```bash
   git push heroku main
   ```

6. Open app:

   ```bash
   heroku open
   ```

---

## 📊 Example Workflow

1. **Login** with Firebase Auth credentials.
2. **Enter bucket + file name** in the UI.
3. **Generate signed URL** (configurable expiration).
4. **Preview JSON** metadata and extracted claims.
5. **Ingest to Firestore** → claims are chunked and stored with progress reports.
```
