# # app/services/firestore_service.py
from config.config import db, logger
from firebase_admin import firestore

def get_or_create_user(normalized_phone):
    doc_ref = db.collection('user_event_tracking').document(normalized_phone)
    doc = doc_ref.get()
    if doc.exists:
        return doc_ref, doc.to_dict()
    else:
        data = {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        doc_ref.set(data)
        return doc_ref, data

def update_user_tracking(normalized_phone, data):
    db.collection('user_event_tracking').document(normalized_phone).update(data)

def update_user_events(normalized_phone, events):
    db.collection('user_event_tracking').document(normalized_phone).update({'events': events})

def event_exists(event_id):
    doc_ref = db.collection(f'AOI_{event_id}').document('info')
    doc = doc_ref.get()
    return doc.exists

def validate_event_id(event_id):
    collections = db.collections()
    valid_event_ids = [col.id.replace('AOI_', '') for col in collections if col.id.startswith('AOI_')]
    return event_id in valid_event_ids

def initialize_event_for_user(event_id, normalized_phone):
    doc_ref = db.collection(f'AOI_{event_id}').document(normalized_phone)
    doc = doc_ref.get()
    if not doc.exists:
        doc_ref.set({'name': None, 'interactions': [], 'event_id': event_id})

def get_initial_message(event_id):
    doc_ref = db.collection(f'AOI_{event_id}').document('info')
    doc = doc_ref.get()
    default_initial_message = "Thank you for agreeing to participate..."
    if doc.exists:
        data = doc.to_dict()
        return data.get('initial_message', default_initial_message)
    return default_initial_message

def event_has_extra_questions(event_id):
    doc_ref = db.collection(f'AOI_{event_id}').document('info')
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        extra = data.get('extra_questions', {})
        return any(q.get('enabled') for q in extra.values())
    return False

def get_ordered_extra_questions(event_id):
    doc_ref = db.collection(f'AOI_{event_id}').document('info')
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        extra = data.get('extra_questions', {})
        enabled = {k: v for k, v in extra.items() if v.get('enabled')}
        ordered = sorted(enabled.items(), key=lambda item: item[1].get('order', 9999))
        keys = [k for k, v in ordered]
        questions = {k: v for k, v in enabled.items()}
        return questions, keys
    return {}, []

def get_event_user_data(event_id, normalized_phone):
    doc_ref = db.collection(f'AOI_{event_id}').document(normalized_phone)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return {}

def update_event_user_field(event_id, normalized_phone, data):
    db.collection(f'AOI_{event_id}').document(normalized_phone).update(data)

def append_event_interaction(event_id, normalized_phone, interaction):
    db.collection(f'AOI_{event_id}').document(normalized_phone).update({
        'interactions': firestore.ArrayUnion([interaction])
    })

def get_completion_message(event_id):
    doc_ref = db.collection(f'AOI_{event_id}').document('info')
    doc = doc_ref.get()
    default_message = "Thank you. You have completed this survey!"
    if doc.exists:
        data = doc.to_dict()
        return data.get('completion_message', default_message)
    return default_message

def update_event_timestamp(events, event_id, current_time, add_if_missing=False):
    updated = False
    for event in events:
        if event.get('event_id') == event_id:
            event['timestamp'] = current_time.isoformat()
            updated = True
            break
    if not updated and add_if_missing:
        events.append({'event_id': event_id, 'timestamp': current_time.isoformat()})
    return events



# (If you want to further encapsulate Firestore calls, you could move
# direct `db.collection(...)` calls here. For now it's a straight pass-through.)

from config.config import db

def get_user_tracking_ref(normalized_phone):
    return db.collection('user_event_tracking').document(normalized_phone)

def get_event_info_ref(event_id):
    return db.collection(f'AOI_{event_id}').document('info')

def get_participant_doc_ref(event_id, phone):
    return db.collection(f'AOI_{event_id}').document(phone)

#These functions will be used in the upcoming refactoring stages —
# at the moment, they are not being actively used.
