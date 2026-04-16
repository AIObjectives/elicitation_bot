# AOI Cloud Data Extraction Service — GCP Cloud Function

Replaces the AWS Lambda version with a Google Cloud Function. AWS services are swapped for GCP equivalents:

| AWS | GCP |
|-----|-----|
| Lambda | Cloud Functions (HTTP trigger) |
| S3 | Cloud Storage |
| SES | Gmail SMTP (via `smtplib`) |

---

## Environment Variables

Set these in the Cloud Function's runtime environment (or a `.env` file for local dev):

| Variable | Description |
|---|---|
| `FIREBASE_CREDENTIALS_JSON` | Firebase Admin SDK credentials JSON (as a string) |
| `GCS_BUCKET_NAME` | GCP Cloud Storage bucket for CSV uploads |
| `GMAIL_APP_PASSWORD` | Gmail App Password for the sender account |
| `EMAIL_SENDER` | Sender Gmail address (default: `info@talktothecity.org`) |

---

## Prerequisites

### 1. Create a GCS Bucket

```bash
gcloud storage buckets create gs://YOUR_BUCKET_NAME --location=us-central1
```

### 2. Set Up Gmail SMTP

- Enable 2-Step Verification on the sending Gmail account
- Generate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- Use that App Password as `GMAIL_APP_PASSWORD` (not your regular Gmail password)

### 3. Service Account Permissions

The Cloud Function's service account needs the following roles to generate signed GCS URLs:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SA@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

---

## Deploy

```bash
gcloud functions deploy csv-handler \
  --gen2 \
  --runtime=python312 \
  --region=us-central1 \
  --source=. \
  --entry-point=csv_handler \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars GCS_BUCKET_NAME=YOUR_BUCKET,EMAIL_SENDER=info@talktothecity.org,GMAIL_APP_PASSWORD=YOUR_APP_PASSWORD \
  --set-env-vars FIREBASE_CREDENTIALS_JSON="$(cat path/to/firebase_credentials.json)"
```

> For `FIREBASE_CREDENTIALS_JSON`, it's safer to use Secret Manager instead:
> ```bash
> gcloud secrets create firebase-credentials --data-file=path/to/firebase_credentials.json
> gcloud functions deploy csv-handler ... \
>   --set-secrets FIREBASE_CREDENTIALS_JSON=firebase-credentials:latest
> ```

---

## Usage

```
https://REGION-PROJECT_ID.cloudfunctions.net/csv-handler?email=recipient@example.com&collections=event1,event2
```

---

## Local Development

```bash
pip install -r requirements.txt
functions-framework --target=csv_handler --port=8080
```

Then call:
```
http://localhost:8080?email=test@example.com&collections=event1
```
