# Firebase User Event Management Tool

This repository contains a suite of standalone Python scripts (“tools”) for managing Firestore collections related to user-event tracking, question management, data export, and event initialization. Each tool can be run independently to perform specific maintenance or data‐gathering tasks.

---

## Table of Contents

1. [Tools Overview](#tools-overview)
2. [Prerequisites & Setup](#prerequisites--setup)
3. [Tools & Usage](#tools--usage)

   1. [1. Manage Conference Data](#1-manage-conference-data)
   2. [2. Add Event Question](#2-add-event-question)
   3. [3. Copy Firestore Collection](#3-copy-firestore-collection)
   4. [4. Export Collection to CSV](#4-export-collection-to-csv)
   5. [5. Initialize or Update Listener-Mode Event](#5-initialize-or-update-listener-mode-event)
4. [Common Configuration](#common-configuration)
5. [Detailed Function References](#detailed-function-references)
6. [Example Outputs](#example-outputs)
7. [Notes & Best Practices](#notes--best-practices)

---

## Tools Overview

Below is a brief description of each script (all located under the `tools/` directory). You can run each one separately, as needed:

1. **`manage_conference_data.py`**

   * Fetches and analyzes all user‐event tracking data (Firestore `user_event_tracking` collection).
   * Offers two deletion routines:

     * Delete users inactive before a specified cutoff date
     * Delete or update users by a specific event ID

2. **`add_event_question.py`**

   * Adds a new question entry to the `questions` array inside an event’s `info` document (Firestore `AOI_{event_id}/info`).

3. **`copy_firestore_collection.py`**

   * Recursively copies one Firestore collection (and its nested subcollections) into another.

4. **`export_collection_to_csv.py`**

   * Exports all user interactions (excluding bot responses) from one or more Firestore event collections into local CSV files.

5. **`initialize_listener_event.py`**

   * Creates or overwrites an event’s `info` document for “listener‐mode” conferences, including fields such as `event_name`, `event_location`, `extra_questions`, and initial/welcome messages.
   * Also allows adding or updating a single extra question to an existing event’s `extra_questions` map.

---

## Prerequisites & Setup

1. **Python Environment**

   * Python 3.8 or later installed.
   * Package dependencies (in `requirements.txt`):

     ```text
     firebase-admin
     google-cloud-firestore
     ```
   * Install them with:

     ```bash
     pip install -r requirements.txt
     ```

2. **Firebase Configuration**

   * Obtain a Firebase Admin SDK service account key (a JSON file).
   * For each script, update the `credentials.Certificate(...)` path to point to your downloaded key file, e.g.:

     ```python
     cred = credentials.Certificate('/path/to/your-service-account-key.json')
     firebase_admin.initialize_app(cred)
     ```
   * Ensure Firestore has the required collections (`user_event_tracking`, `AOI_{event_id}`, etc.) for your use case.

3. **Firestore Rules & Access**

   * The service account must have read/write access to Firestore.
   * Double-check your Firestore security rules so that these scripts can perform the necessary read/write operations.

4. **Directory Structure**

   ```
   project_root/
   ├── tools/
   │   ├── manage_conference_data.py
   │   ├── add_event_question.py
   │   ├── copy_firestore_collection.py
   │   ├── export_collection_to_csv.py
   │   └── initialize_listener_event.py
   ├── requirements.txt
   └── README.md
   ```

---

## Tools & Usage

Below is a detailed breakdown of each tool, including how to configure and run them.

### 1. Manage Conference Data

**File:** `tools/manage_conference_data.py`

#### Purpose

* Fetches all documents from the `user_event_tracking` collection.
* Computes:

  * Last‐activity timestamp per user
  * Users associated with multiple events
  * Number of users per event
* Provides two deletion routines (both support a dry-run):

  1. **Delete by Last Activity**: Remove users inactive before a specified cutoff date.
  2. **Delete by Event ID**: Remove or update users associated with a specific event ID.

#### How to Run

```bash
python tools/manage_conference_data.py
```

#### Script Flow

1. **Initialize Firebase**

   * Reads the service account JSON (path hardcoded near the top).
2. **Fetch & Summarize**

   * `get_user_event_tracking_data()`:

     * Streams all docs in `user_event_tracking`
     * Builds `user_data`, `event_users`, and `users_with_multiple_events`
     * Prints summary (total events, user counts, multiple-event users).
3. **Deletion Options**

   * **Delete by Last Activity**

     * Prompts: “Type ‘yes’ to delete by last activity.”
     * `delete_users_by_criteria(user_data, dry_run=True)`

       * Asks for cutoff date (`YYYY-MM-DD`).
       * In dry-run, lists users who would be deleted.
       * If confirmed (`yes`), runs again with `dry_run=False` to delete.
   * **Delete by Event ID**

     * Prompts: “Type ‘yes’ to delete by event ID.”
     * `delete_users_by_event_id(user_data, dry_run=True)`

       * Asks for an `event_id`.
       * Lists users who would be deleted or updated (if they have other events).
       * If confirmed, runs with `dry_run=False` to perform deletion/update.

#### Key Functions

* `get_user_event_tracking_data()`: Returns `(user_data, event_users, users_with_multiple_events)`.
* `delete_users_by_criteria(user_data, dry_run=True)`: Dry-run or delete by cutoff date.
* `delete_users_by_event_id(user_data, dry_run=True)`: Dry-run or delete/update by event ID.

---

### 2. Add Event Question

**File:** `tools/add_event_question.py`

#### Purpose

* Prompts for an `event_id` and a `new_question_text`.
* Appends the new question (with an automatically generated `id` and `asked_count = 0`) to the existing `questions` array in the Firestore document `AOI_{event_id}/info`.

#### How to Run

```bash
python tools/add_event_question.py
```

#### Script Flow

1. **Initialize Firebase**

   * Uses the service account JSON path at top of the file.
2. **Prompt User**

   * Asks for `event_id` (e.g., `Utopia_Network`).
   * Asks for `new_question_text`.
3. **Add Question**

   * Reads `AOI_{event_id}/info` document.
   * Validates that the `questions` field exists.
   * Creates `new_question_entry` with:

     ```json
     {
       "id": <current_length_of_questions>,
       "text": "<new_question_text>",
       "asked_count": 0
     }
     ```
   * Updates Firestore (appending to the `questions` array).
4. **Confirmation**

   * Prints success or error messages.

---

### 3. Copy Firestore Collection

**File:** `tools/copy_firestore_collection.py`

#### Purpose

* Asks for a **source** and **target** collection name.
* Recursively copies every document (and its nested subcollections) from `<source>` into `<target>`.

#### How to Run

```bash
python tools/copy_firestore_collection.py
```

#### Script Flow

1. **Initialize Firebase**

   * Reads service account JSON (hardcoded path near the top).
2. **Prompt User**

   * “Enter source collection name:” (e.g., `Week1_TAICA_COPY`)
   * “Enter target collection name:” (e.g., `Backup_Week1_TAICA_COPY`)
3. **Copy Logic**

   * `copy_collection(source_ref, target_ref)` iterates over `source_ref.stream()`.
   * For each document:

     * Writes `target_ref.document(doc.id).set(doc.to_dict())`
     * Recursively copies nested subcollections via `copy_subcollection(...)`.
4. **Completion**

   * Prints “Copy completed.”

---

### 4. Export Collection to CSV

**File:** `tools/export_collection_to_csv.py`

#### Purpose

* If the UI isn’t available (or for any other reason), fetch all user messages (excluding bot responses) and additional fields from one or more Firestore event collections locally.
* Dynamically generate a CSV for each collection and save it as `<collection_name>.csv`.

#### How to Run

```bash
python tools/export_collection_to_csv.py
```

#### Script Flow

1. **Initialize Firebase**

   * Loads service account JSON from `xxx.json`.
2. **Specify Collections**

   * Modify the `collection_names` list in the script (e.g., `["AOI_3_TAICA_3", "AOI_5_TAICA_5"]`).
3. **Fetch & Clean Data**

   * `get_all_user_inputs(db, collection_name)`:

     * Streams each document in the specified collection.
     * Skips the `info` document by `doc.id == 'info'`.
     * For every user‐document (`doc.id` = phone number):

       * Gathers `"message"` fields from interactions where `'response'` is not present (i.e., user messages).
       * Concatenates and cleans text into a single “comment‐body” string.
       * Copies `"name"` and any additional fields (excluding `interactions`, `name`, `limit_reached_notified`, `event_id`).
       * Returns a mapping:

         ```python
         {
           "<phone_number>": {
             "name": "...",
             "comment-body": "cleaned user messages",
             <other_fields>: ...
           },
           ...
         }
         ```
4. **Generate CSV**

   * `generate_dynamic_csv(all_messages)`:

     * Inspects all field keys across all users to build a unified header row:

       ```
       comment-id, <sorted field names...>
       ```
     * For each user entry, writes a row `[index, value_for_field1, value_for_field2, …]`.
   * Returns CSV content as a string.
5. **Save CSV Locally**

   * Writes the returned CSV string to a file named `<collection_name>.csv`.
6. **Print Status**

   * Confirms “CSV saved as: `<collection_name>.csv`” for each collection processed.

---

### 5. Initialize or Update Listener-Mode Event

**File:** `tools/initialize_listener_event.py`

#### Purpose

* Creates or overwrites the Firestore document `AOI_{event_id}/info` to set up a “listener‐mode” conference.
* Populates fields such as:

  * `event_initialized` (Boolean)
  * `event_name`, `event_location`, `event_background`
  * `event_date`
  * `welcome_message`, `initial_message`, `completion_message`
  * `languages` (list)
  * `extra_questions` (map of question keys to configuration)
* Also provides a function to add or update a single `extra_question` entry without overwriting existing questions.

#### How to Run

```bash
python tools/initialize_listener_event.py
```

#### Script Flow

1. **Initialize Firebase**

   * Uses service account JSON (hardcoded path near the top).
2. **Initialize a Brand-New Event**

   * The script’s `__main__` block includes an example usage:

     ```python
     event_id = "xxx"
     event_name = "xxx"
     event_location = "Taiwan"
     event_background = "..."
     event_date = "2025"
     languages = ["Mandarin", "English"]
     initial_message = "歡迎您..."
     completion_message = "Thank you ..."
     initialize_event_collection(...)
     ```
   * `initialize_event_collection(...)` calls `info_doc_ref.set(...)` with a dict containing all fields, including an `extra_questions` map.
   * **Warning:** This will overwrite any existing fields in `AOI_{event_id}/info`.
3. **Add or Update a Single Extra Question**

   * Example commented‐out code in the script:

     ```python
     add_extra_question(
         event_id="DemoEvent2025",
         question_key="ExtraQuestion5",
         text="What is your favorite color?",
         enabled=True,
         order=5,
         function_id=None
     )
     ```
   * `add_extra_question(...)` fetches the existing `info` doc, merges or adds the new question key into `extra_questions`, and updates Firestore.
   * Does **not** overwrite other keys in `extra_questions`.
4. **Logging**

   * Uses Python’s `logging` module at `INFO` level to report success or warnings.

---

## Common Configuration

All tools rely on a Firebase Admin SDK service account JSON file. You must:

1. **Download**

   * Go to your Firebase Console → Settings → Service Accounts → Generate New Private Key → Save JSON locally.

2. **Edit Each Script**

   * Near the top of each `.py` file, locate the line:

     ```python
     cred = credentials.Certificate('xxx.json')
     ```
   * Replace `'xxx.json'` with the relative or absolute path to your downloaded key, e.g.:

     ```python
     cred = credentials.Certificate('/home/user/keys/firebase-adminsdk.json')
     ```

3. **Install Dependencies**

   * The only required dependency (besides standard library) is:

     ```
     firebase-admin
     ```
   * Confirm with:

     ```bash
     pip install firebase-admin
     ```

---

## Detailed Function References

### `get_user_event_tracking_data()`

* **Location:** `tools/manage_conference_data.py`
* **Returns:**

  * `user_data`: `Dict[str, { events, last_activity, awaiting_event_id, current_event_id }]`
  * `event_users`: `Dict[str, Set[str]]` (maps `event_id` → set of users)
  * `users_with_multiple_events`: `List[str]`

### `delete_users_by_criteria(user_data, dry_run=True)`

* **Location:** `tools/manage_conference_data.py`
* **Parameters:**

  * `user_data`: from `get_user_event_tracking_data()`
  * `dry_run` (bool): If `True`, only print users that would be deleted; if `False`, actually delete.
* **Behavior:**

  1. Prompts for cutoff date (`YYYY-MM-DD`).
  2. Determines which users have `last_activity < cutoff_date` or no `last_activity`.
  3. If `dry_run`, list them and prompt “Type ‘yes’ to confirm actual deletion.”
  4. If confirmed, reruns with `dry_run=False` and deletes those users from:

     * `user_event_tracking`
     * each relevant `AOI_{event_id}` collection.

### `delete_users_by_event_id(user_data, dry_run=True)`

* **Location:** `tools/manage_conference_data.py`
* **Parameters:**

  * `user_data`: from `get_user_event_tracking_data()`
  * `dry_run` (bool): same pattern as above.
* **Behavior:**

  1. Prompts for `event_id_to_delete`.
  2. Gathers:

     * `users_to_delete` (users whose only event is `event_id_to_delete`)
     * `users_to_update` (users who have other events → update their event list)
  3. If `dry_run`, list them, then prompt “Type ‘yes’ to confirm actual changes.”
  4. If confirmed, reruns with `dry_run=False` and:

     * Deletes entire user doc for `users_to_delete` from `user_event_tracking` and `AOI_{event_id}`.
     * Updates `events` array for `users_to_update` and deletes from `AOI_{event_id}`.

### `add_question_to_event(event_id, new_question)`

* **Location:** `tools/add_event_question.py`
* **Parameters:**

  * `event_id` (str): Firestore event collection suffix (e.g., `"Utopia_Network"`)
  * `new_question` (str): Text of the new question
* **Behavior:**

  1. Reads `AOI_{event_id}/info`.
  2. Validates `questions` array exists.
  3. Appends a new dict:

     ```json
     {"id": <current_length>, "text": new_question, "asked_count": 0}
     ```
  4. Updates Firestore.

### `copy_collection(source_collection_name, target_collection_name)`

* **Location:** `tools/copy_firestore_collection.py`
* **Parameters:**

  * `source_collection_name` (str)
  * `target_collection_name` (str)
* **Behavior:**

  1. Streams all docs from `db.collection(source_collection_name)`.
  2. For each document:

     * Writes the doc’s `to_dict()` to `db.collection(target_collection_name).document(doc.id)`
     * Recursively copies each subcollection via `copy_subcollection(...)`.

### `get_all_user_inputs(db, collection_name)`

* **Location:** `tools/export_collection_to_csv.py`
* **Parameters:**

  * `db`: Firestore client (`firestore.client()`)
  * `collection_name` (str)
* **Returns:**

  * `all_messages`: `Dict[phone_number, { name, comment-body, <other fields> }]`
* **Behavior:**

  1. Streams each document in `collection_name`.
  2. Skips `doc.id == 'info'`.
  3. Extracts only user‐sent messages (`"message"`) from `interactions` array (ignoring any dicts with `"response"`).
  4. Merges them into a single string, `comment-body`.
  5. Copies the `name` field and any other fields except:

     * `interactions`, `name`, `limit_reached_notified`, `event_id`.

### `generate_dynamic_csv(all_messages)`

* **Location:** `tools/export_collection_to_csv.py`
* **Parameters:**

  * `all_messages`: from `get_all_user_inputs(...)`
* **Returns:**

  * CSV content (string)
* **Behavior:**

  1. Builds a header row containing `comment-id` + all unique keys from `all_messages`.
  2. For each user (in insertion order), writes `[index, value_for_key1, value_for_key2, …]`.
  3. Joins them into a multi-line CSV string.

### `initialize_event_collection(...)`

* **Location:** `tools/initialize_listener_event.py`
* **Parameters:**

  * `event_id`, `event_name`, `event_location`, `event_background`, `event_date`, `languages`, `initial_message`, `completion_message`
* **Behavior:**

  1. Creates or overwrites `AOI_{event_id}/info` with a dictionary:

     ```json
     {
       "event_initialized": True,
       "event_name": "...",
       "event_location": "...",
       "event_background": "...",
       "event_date": "...",
       "welcome_message": "...",
       "initial_message": "...",
       "completion_message": "...",
       "languages": [...],
       "extra_questions": { ... }  
     }
     ```
  2. Example `extra_questions` (in Chinese/English) is included.
  3. Prints an INFO log:

     ```
     [initialize_event_collection] Event '...' initialized/overwritten with extra questions.
     ```

### `add_extra_question(event_id, question_key, text, enabled=True, order=1, function_id=None)`

* **Location:** `tools/initialize_listener_event.py`
* **Parameters:**

  * `event_id` (str)
  * `question_key` (str): e.g., `"ExtraQuestion5"`
  * `text` (str)
  * `enabled` (bool)
  * `order` (int)
  * `function_id` (str, optional)
* **Behavior:**

  1. Reads `AOI_{event_id}/info`.
  2. Merges or creates `extra_questions[question_key] = { enabled, text, order, (id if provided) }`.
  3. Updates Firestore.
  4. Logs:

     ```
     [add_extra_question] Added/updated question '...' in event '...'.
     ```

---

## Example Outputs

Below are illustrative snippets showing how each tool prints status and results:

### 1. Manage Conference Data

```
Fetching user-event tracking data...

Total number of different events: 4

Number of users in each event:
Event 'Utopia_Network': 23 users
Event 'TAICA_3': 15 users
Event 'DemoEvent2025': 8 users
Event 'Test_Event': 5 users

Total number of users with more than one event: 2

Users with more than one event:
User 'user123' is in events: ['Utopia_Network', 'TAICA_3']
User 'user456' is in events: ['DemoEvent2025', 'Test_Event']

Delete users by last activity? Type 'yes' to proceed: yes

Enter cutoff date (YYYY-MM-DD): 2025-01-01

[DRY RUN] Users to be deleted:
  - user789
  - user999

Total: 2 user(s)

Dry run only. No changes made.
Type 'yes' to confirm actual deletion: no
Aborted.

Delete users by event ID? Type 'yes' to proceed: yes

Enter event ID to purge users from: DemoEvent2025

[DRY RUN] Affected users for event 'DemoEvent2025':
  - user111 (will be fully deleted)
  - user222 (events updated)

Dry run only. No changes made.
Type 'yes' to confirm actual deletion/update: yes

Deleting user 'user111' from 'user_event_tracking'...
Deleting user 'user111' from 'AOI_DemoEvent2025'...
Updating user 'user222'—removing event 'DemoEvent2025'...
Deleting user 'user222' from 'AOI_DemoEvent2025'...
Deletion/Update completed.
```

### 2. Add Event Question

```
Enter event ID (e.g., 'Utopia_Network'): DemoEvent2025
Enter the new question text: What is your favorite programming language?
✅ Successfully added question to event 'DemoEvent2025'.
```

### 3. Copy Firestore Collection

```
Enter source collection name: Week1_TAICA_COPY
Enter target collection name: Archive_Week1_TAICA_COPY
Copying collection 'Week1_TAICA_COPY' → 'Archive_Week1_TAICA_COPY'...
Copy completed.
```

### 4. Export Collection to CSV

```
Fetching data from collection: AOI_3_TAICA_3
CSV saved as: AOI_3_TAICA_3.csv

Fetching data from collection: AOI_5_TAICA_5
CSV saved as: AOI_5_TAICA_5.csv
```

Generated file names:

```
AOI_3_TAICA_3.csv
AOI_5_TAICA_5.csv
```

### 5. Initialize Listener-Mode Event

```bash
$ python tools/initialize_listener_event.py
```

(Since this script’s `__main__` block uses hardcoded example data, no interactive prompts appear unless you modify the code.
Typical output:)

```
INFO:root:[initialize_event_collection] Event 'xxx' initialized/overwritten with extra questions.
```

To add a single extra question (uncomment & adjust example lines at bottom):

```
INFO:root:[add_extra_question] Added/updated question 'ExtraQuestion5' in event 'DemoEvent2025'.
```

---

## Notes & Best Practices

1. **Dry-Run Safety**

   * Both deletion routines in `manage_conference_data.py` default to `dry_run=True`.
   * Always review the printed user lists before confirming deletion.

2. **Overwriting `info` Documents**

   * `initialize_listener_event.py` will **overwrite** any existing fields in `AOI_{event_id}/info`.
   * If you need to preserve existing `extra_questions`, use `add_extra_question()` instead of full initialization.

3. **CSV Export Considerations**

   * The CSV generator merges all user messages into a single “comment-body” field.
   * If you need more granular exports (e.g., per‐message timestamp), consider customizing `get_all_user_inputs()`.

4. **Firestore Billing & Quotas**

   * Streaming large collections may incur read costs.
   * Deleting many documents one-by-one may be slow or exceed rate limits.
   * For mass deletes, consider using Firestore’s batch operations or Cloud Functions.

5. **Error Handling**

   * Each script prints warnings if Firestore documents or fields are missing.
   * If a path’s credentials or collection names are incorrect, the script will raise an exception.

6. **Customization & Extension**

   * Feel free to modify the hardcoded examples (e.g., collection lists, event fields).
   * Each tool is designed to be self‐contained; you can copy/paste its contents into your own utilities.

---

With all five tools now documented and ready to run, you have a complete toolkit for:

* Managing user‐event tracking data
* Cleaning up or archiving Firestore collections
* Exporting user interactions to CSV
* Initializing and customizing new “listener‐mode” events

Simply edit the credential paths at the top of each file, install dependencies, and run whatever script matches your current need.

