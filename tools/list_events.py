#!/usr/bin/env python3
"""
List all events in the elicitation_bot_events collection
"""
import firebase_admin
from firebase_admin import credentials, firestore
import os, json

FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON")

if not FIREBASE_CREDENTIALS_JSON:
    raise RuntimeError("Missing FIREBASE_CREDENTIALS_JSON environment variable")

cred = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS_JSON))
firebase_admin.initialize_app(cred)
db = firestore.client()

print("=" * 70)
print("LISTING ALL EVENTS IN elicitation_bot_events COLLECTION")
print("=" * 70)

# List all events
events = db.collection('elicitation_bot_events').stream()

count = 0
for event in events:
    count += 1
    event_data = event.to_dict()
    print(f"\n{count}. Event ID: {event.id}")
    print(f"   Name: {event_data.get('event_name', 'N/A')}")
    print(f"   Mode: {event_data.get('mode', 'N/A')}")
    print(f"   Initialized: {event_data.get('event_initialized', False)}")
    print(f"   Owner: {event_data.get('owner_id', 'Not set')}")

    # Check if event has participants
    participants = db.collection('elicitation_bot_events').document(event.id).collection('participants').limit(1).stream()
    has_participants = len(list(participants)) > 0
    print(f"   Has participants: {has_participants}")

if count == 0:
    print("\n⚠️  NO EVENTS FOUND in elicitation_bot_events collection!")
    print("\nPossible issues:")
    print("1. Events might be in the old AOI_* collections")
    print("2. Wrong Firebase project/credentials")
    print("3. Service account lacks read permissions")

    # Check for old-style collections
    print("\n" + "=" * 70)
    print("CHECKING FOR OLD-STYLE AOI_* COLLECTIONS")
    print("=" * 70)

    collections = db.collections()
    aoi_collections = [col.id for col in collections if col.id.startswith('AOI_')]

    if aoi_collections:
        print(f"\n✓ Found {len(aoi_collections)} old-style AOI_* collections:")
        for col_name in aoi_collections[:10]:  # Show first 10
            print(f"   - {col_name}")
        if len(aoi_collections) > 10:
            print(f"   ... and {len(aoi_collections) - 10} more")
    else:
        print("\n✗ No AOI_* collections found either")
else:
    print(f"\n{'=' * 70}")
    print(f"Total events found: {count}")
    print(f"{'=' * 70}")
