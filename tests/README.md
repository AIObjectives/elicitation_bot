### ⚠️ Caution: Test Coverage Disclaimer

> **Note:** While the unit test scaffolding is complete and logically aligned with the application's structure, these tests have **not yet been fully verified end-to-end** with live Twilio or OpenAI API interactions.

If you'd like to test and expand the coverage yourself:

* ✅ Use the provided `TestClient` tests to simulate local FastAPI responses.
* 🔄 For true integration testing (including Twilio WhatsApp messages and OpenAI completions), follow the Twilios Documentation** :

  * Deploy the production version on Heroku and connect a Twilio Business WhatsApp number (**recommended**), or
  * Use Twilio's sandbox in conjunction with `localtunnel` or `ngrok` for a limited local testing experience (**experimental and may require config tweaks**).

> Until full verification is completed, please rely on the main deployed production instance for critical usage or demos.

---


Below covers:

1. **Automated Unit Tests** (using FastAPI’s `TestClient`)
2. **Integration / End-to-End Testing** with Twilio
3. **Twilio Sandbox vs. “Real” Business Account** (and configuration notes)
4. **Deploying to Heroku for Full-System Verification**
5. **Localtunnel (or ngrok) Setup for Local Testing**

---

## 📂 `tests/` Overview

```
tests/
├── __init__.py
├── test_message_handler.py
└── README.md         ← (this document)
```

### 1. Automated Unit Tests

**Purpose**

* Quickly verify that core routing and handler logic behave as expected when given well-formed or malformed inputs.
* Run locally as part of continuous integration (CI).


**Key Points to Note for Automated Unit Tests**

* We used `pytest` and FastAPI’s `TestClient`.
* We stubbed or monkey-patched all Firestore calls so no real database is hit. In a real CI pipeline, you may spin up the Firebase Emulator instead of stubbing.
* We covered:

  1. Missing required fields → HTTP 422
  2. New user (⌀ `current_event_id`) → prompt for event ID
  3. `finalize` / `finish` → sends correct completion message
  4. Inactivity selection / invalid event index → “invalid event selection” prompt

Feel free to write additional `@pytest.mark.parametrize` tests for:

* “change name \[new]” → updates Firestore doc, replies accordingly
* “change event \[id]” → sets `awaiting_event_change_confirmation = True`, etc.
* Extra‐questions flow: simulate audio upload + transcription stub
* Normal conversation flow: stub out OpenAI calls to return a canned “assistant” response

---

### 2. Integration / End-to-End Testing

Automated unit tests only verify that your handler logic doesn’t raise errors. To fully test “Twilio → FastAPI → Firestore → OpenAI → Twilio” interactions, you have two main approaches:

#### A. Deploy to Heroku & Use a Twilio Business WhatsApp Number

1. **Provision a Twilio Business WhatsApp Number**

   * Sign up for Twilio and request a WhatsApp–enabled sender.
   * Follow Twilio’s official guide for “WhatsApp Business API → Sandbox → Production transition.”
   * You’ll need to submit a request to Facebook/Meta via Twilio to get a permanent WhatsApp “From” number.
   * Twilio docs:

     * [WhatsApp API overview](https://www.twilio.com/whatsapp)
     * [Provisioning a WhatsApp Sender](https://www.twilio.com/docs/whatsapp/api)

2. **Deploy Your FastAPI App to Heroku**

   * Push your refactored repository to a Git remote.
   * Create a new Heroku app:

     ```bash
     heroku login
     heroku create your-app-name
     git push heroku main
     ```
   * Configure environment variables on Heroku for all keys:

     ```bash
     heroku config:set \
       OPENAI_API_KEY="…" \
       TWILIO_ACCOUNT_SID="…" \
       TWILIO_AUTH_TOKEN="…" \
       TWILIO_NUMBER="whatsapp:+1234567890" \
       ASSISTANT_ID="…" \
       FIREBASE_CREDENTIALS_JSON='{"type": …}'  
     ```
   * Ensure your `Procfile` is present and correct:

     ```
     web: uvicorn app.main:app --host=0.0.0.0 --port=${PORT:-5000}
     ```
   * Run `heroku open` to confirm the endpoint is live at `https://your-app-name.herokuapp.com/message/`.

3. **Configure Twilio’s Webhook**

   * In your Twilio console under “Programmable Messaging → WhatsApp → Sandbox → Sandbox Settings,” set the “WHEN A MESSAGE COMES IN” webhook to:

     ```
     https://your-app-name.herokuapp.com/message/
     ```
   * For a “Production” (Business) WhatsApp number, you do the same under the “WhatsApp Senders” section.

4. **Send Tests from Your WhatsApp**

   * From the phone that’s “approved” to message your Twilio WhatsApp number, open a WhatsApp chat to that number.
   * Type “Hello” → FastAPI should receive `Body="Hello"`, store or fetch your “user\_event\_tracking” doc, and reply.
   * Walk through all possible paths:

     1. Send a random string → “Welcome! Please provide your event ID to proceed.”
     2. Provide a valid event ID → Extra‐questions flow or “welcome message.”
     3. Try “change name John” → bot updates Firestore and replies.
     4. Simulate audio: send a voice note → confirm transcription branch.

5. **Inspect Firestore Data**

   * Go to your Firebase Console, look up `user_event_tracking` and `AOI_{event_id}` collections to confirm data was written correctly.
   * Confirm that the FIrebase rules allow server‐side writes.

6. **Teardown / Cleanup**

   * After testing, you can remove your Twilio sandbox configurations or un‐provision your “Production” WhatsApp sender to avoid extra charges.

#### B. Use Twilio’s WhatsApp “Sandbox” Mode (Local Testing)

> **Note:** The sandbox is limited:
>
> * You must manually “join” the sandbox from your personal WhatsApp number each time.
> * Some message types (e.g., templates) may not work.
> * Sandbox phone numbers can change.

1. **Enable the Twilio WhatsApp Sandbox**

   * In Twilio Console → Programmable Messaging → “Try it out” → “WhatsApp Sandbox.”
   * Follow the instructions to send a unique join code (e.g., `join awesome-sandbox`) from your phone’s WhatsApp to Twilio’s sandbox number.
   * Confirm that your number appears under “Participants.”

2. **Run FastAPI Locally via Localtunnel (or ngrok)**

   * Start your FastAPI server on port 5000 (or any other port):

     ```bash
     uvicorn app.main:app --reload --port 5000
     ```
   * In a new terminal tab:

     ```bash
     # Install ngrok or localtunnel if you haven’t already:
     npm install -g localtunnel
     # or: brew install ngrok

     # Then tunnel port 5000:
     lt --port 5000
     # or: ngrok http 5000
     ```
   * You’ll see a public URL, e.g. `https://random-string.loca.lt` or `https://abcd1234.ngrok.io`.

3. **Update Your Twilio Sandbox Webhook**

   * In the Sandbox settings, set “WHEN A MESSAGE COMES IN” to:

     ```
     https://<your‐public‐tunnel>.ngrok.io/message/
     ```
   * If your server is on port 5000 locally, Twilio’s requests will be forwarded to your local FastAPI.

4. **Adjust Configuration for Sandbox Mode**

   * In `config/config.py`, you may need to detect if you’re running locally vs. Heroku. For example:

     ```python
     import os
     from decouple import config as _config

     ENV = os.getenv("ENV", "development")
     if ENV == "production":
         TWILIO_NUMBER = _config("TWILIO_NUMBER")
     else:
         # Sandbox “From” is usually "whatsapp:+14155238886"
         TWILIO_NUMBER = _config("TWILIO_SANDBOX_NUMBER", default="whatsapp:+14155238886")
     ```
   * In your `.env`:

     ```
     ENV=development
     TWILIO_ACCOUNT_SID=…
     TWILIO_AUTH_TOKEN=…
     TWILIO_SANDBOX_NUMBER="whatsapp:+14155238886"
     ```
   * Locally, you send messages to/from `whatsapp:+14155238886`; in production, it’s your “real” WhatsApp number.

5. **Testing Steps in Sandbox**

   * From your personal WhatsApp, send a text to the sandbox number (`+1 415 523 8886`).
   * Confirm you receive responses from FastAPI (via your tunnel).
   * Try:

     1. Random text → “Welcome! Provide event ID.”
     2. Valid event ID → welcome + extra‐questions.
     3. “change name Mary” → “Your name has been updated to Mary.”
     4. Send a voice note → verify local transcription branch (you may need to stub out real Whisper API calls).

6. **Limitations**

   * Sandbox sometimes reuses the same “From” number. You may need to manually clear participant state after each test.
   * If your code expects a real Twilio “MediaUrl0” link in production, sandbox media delivery can differ slightly—confirm `Content-Type: audio/ogg; codecs=opus`.
   * Some Twilio template messages or interactive buttons are not available in sandbox.

---

### 3. “Information” Section (How to Test the Full System)

1. **Automated Tests (CI)**

   * Run locally:

     ```bash
     pytest --maxfail=1 --disable-warnings -q
     ```
   * In CI (e.g., GitHub Actions), set up:

     ```yaml
     name: CI
     on: [push, pull_request]
     jobs:
       test:
         runs-on: ubuntu-latest
         steps:
           - uses: actions/checkout@v2
           - name: Set up Python
             uses: actions/setup-python@v2
             with:
               python-version: '3.10'
           - name: Install dependencies
             run: pip install -r requirements.txt
           - name: Run tests
             run: pytest
     ```
   * **Caveat:** These tests only validate the handler logic. They do not verify real Twilio or OpenAI calls.

2. **Twilio Sandbox vs. Production (Business WhatsApp)**

   * **Sandbox**

     * Pros: Zero‐cost, quick to set up, no need for Facebook/Meta approval.
     * Cons: Limited features, ephemeral phone number, sometimes restricted media formats.
     * Use: Local testing via ngrok/localtunnel.
     * Docs:

       * [Twilio WhatsApp Sandbox Quickstart](https://www.twilio.com/docs/whatsapp/sandbox)
       * [Incoming Message Webhooks](https://www.twilio.com/docs/whatsapp/tutorial/send-whatsapp-notifications)
   * **Production Biz Number**

     * Pros: Real “From” number, no sandbox limits, can send template messages, HSMs, etc.
     * Cons: Requires Business Verification through Facebook, paid Twilio account.
     * Use: Deploy to Heroku (or any publicly accessible HTTPS endpoint).
     * Docs:

       * [Twilio WhatsApp Business API](https://www.twilio.com/whatsapp/overview)
       * [Provisioning a WhatsApp Sender](https://www.twilio.com/docs/whatsapp/api)

3. **Localtunnel / ngrok**

   * Why: Twilio requires a public HTTPS endpoint.
   * Popular choices:

     * **ngrok** (`ngrok http 5000`)
     * **localtunnel** (`lt --port 5000`)
   * Both will produce a URL like `https://abcd1234.ngrok.io` that you can paste into Twilio’s “Webhook” field for incoming messages.

4. **Heroku Deployment Steps (Full End-to-End)**

   1. **Heroku CLI Setup**

      ```bash
      heroku login
      heroku create <your-app-name>
      ```
   2. **Set Environment Variables**

      ```bash
      heroku config:set \
        ENV=production \
        OPENAI_API_KEY="…" \
        TWILIO_ACCOUNT_SID="…" \
        TWILIO_AUTH_TOKEN="…" \
        TWILIO_NUMBER="whatsapp:+1XXXXXXXXXX" \
        ASSISTANT_ID="…" \
        FIREBASE_CREDENTIALS_JSON='{"type":…}'
      ```
   3. **Push & Migrate**

      ```bash
      git push heroku main
      # (If you ever need migrations for Firestore emulators, run them locally before deploying)
      ```
   4. **Verify Live Endpoint**

      ```bash
      heroku open   # opens https://<your-app-name>.herokuapp.com
      ```
   5. **Configure Twilio Webhook**

      * In Twilio Console → WhatsApp Sender → set “WHEN A MESSAGE COMES IN” to
        `https://<your-app-name>.herokuapp.com/message/`
   6. **Test from Real WhatsApp**

      * Send “hi” → observe Firestore writes and bot replies.
      * Walk through the entire “1–10 Steps” conversation flow.

5. **Example `.env` for Local Development**

   ```ini
   # .env
   ENV=development

   # OpenAI
   OPENAI_API_KEY=sk-…

   # Twilio (Sandbox)
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxx
   TWILIO_SANDBOX_NUMBER="whatsapp:+14155238886"

   # Twilio (Production) – only if you have a business WhatsApp sender
   # TWILIO_NUMBER="whatsapp:+XYYYYYYYYYY"

   # Firebase
   FIREBASE_CREDENTIALS_JSON='{
     "type": "service_account",
     "project_id": "my-project-id",
     …
   }'

   # OpenAI Assistant ID
   ASSISTANT_ID=xxxxxxxxxxxx
   ```

---

### 4. Summary of `tests/` Best Practices

* **Automate what you can**: unit tests should cover all code paths that don’t require real external calls.
* **Stub or Emulate**: use the Firebase emulator or monkey-patch Firestore so CI doesn’t require live Firestore.
* **Manual Integration**: for anything involving Twilio (media transcription, actual WhatsApp delivery), you’ll need either the Sandbox or a live Business account.
* **Local Tunneling**: remember to update your Twilio webhook whenever your tunnel URL changes.
* **Keep Documentation Up to Date**: whenever you add new features (e.g. new “extra questions,” new `/change` commands), add the corresponding unit tests and update this `tests/README.md` so other developers know how to verify.


