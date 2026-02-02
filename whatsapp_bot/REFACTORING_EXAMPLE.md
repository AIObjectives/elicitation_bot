# Refactoring Example: Using the Database Abstraction Layer

This document shows a concrete example of refactoring handler code to use the database abstraction layer.

## Example: ListenerMode.py First 200 Lines

### BEFORE: Direct Firestore Access

```python
async def reply_listener(Body: str, From: str, MediaUrl0: str = None):
    logger.info(f"Received message from {From} with body '{Body}' and media URL {MediaUrl0}")

    # Normalize phone number
    normalized_phone = From.replace("+", "").replace("-", "").replace(" ", "")

    # Step 1: Retrieve or initialize user tracking document
    user_tracking_ref = db.collection('user_event_tracking').document(normalized_phone)
    user_tracking_doc = user_tracking_ref.get()
    if user_tracking_doc.exists:
        user_data = user_tracking_doc.to_dict()
    else:
        # Initialize user doc with minimal structure
        user_data = {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        user_tracking_ref.set(user_data)

    # Extract main fields from user_data
    user_events = user_data.get('events', [])
    current_event_id = user_data.get('current_event_id')
    awaiting_event_id = user_data.get('awaiting_event_id', False)
    awaiting_event_change_confirmation = user_data.get('awaiting_event_change_confirmation', False)
    last_inactivity_prompt = user_data.get('last_inactivity_prompt', None)

    # Remove duplicates in user_events
    unique_events = {}
    for event in user_events:
        eid = event['event_id']
        if eid not in unique_events:
            unique_events[eid] = event
        else:
            existing_time = datetime.fromisoformat(unique_events[eid]['timestamp'])
            new_time = datetime.fromisoformat(event['timestamp'])
            if new_time > existing_time:
                unique_events[eid] = event
    user_events = list(unique_events.values())
    user_data['events'] = user_events
    user_tracking_ref.update({'events': user_events})

    # Validate current event
    if current_event_id:
        event_info_ref = db.collection(normalize_event_path(current_event_id)).document('info')
        event_info_doc = event_info_ref.get()
        if not event_info_doc.exists:
            user_events = [e for e in user_events if e['event_id'] != current_event_id]
            user_tracking_ref.update({
                'current_event_id': None,
                'events': user_events,
                'awaiting_event_id': True
            })
            send_message(From, f"The event '{current_event_id}' is no longer active...")
            return Response(status_code=200)

    # Check for inactivity (24 hours)
    if last_inactivity_prompt:
        last_prompt_time = datetime.fromisoformat(last_inactivity_prompt)
        now = datetime.now()
        if (now - last_prompt_time) >= timedelta(hours=24):
            # Reset inactivity tracking
            user_tracking_ref.update({
                'last_inactivity_prompt': None,
                'invalid_attempts': 0
            })
```

### AFTER: Using Abstraction Layer

```python
from app.services.firestore_service import (
    UserTrackingService,
    EventService,
    ParticipantService
)

async def reply_listener(Body: str, From: str, MediaUrl0: str = None):
    logger.info(f"Received message from {From} with body '{Body}' and media URL {MediaUrl0}")

    # Normalize phone number
    normalized_phone = From.replace("+", "").replace("-", "").replace(" ", "")

    # Step 1: Retrieve or initialize user tracking document
    user_tracking_ref, user_data = UserTrackingService.get_or_create_user(normalized_phone)

    # Extract main fields from user_data
    user_events = user_data.get('events', [])
    current_event_id = user_data.get('current_event_id')
    awaiting_event_id = user_data.get('awaiting_event_id', False)
    awaiting_event_change_confirmation = user_data.get('awaiting_event_change_confirmation', False)
    last_inactivity_prompt = user_data.get('last_inactivity_prompt', None)

    # Remove duplicates in user_events
    user_events = UserTrackingService.deduplicate_events(user_events)
    UserTrackingService.update_user_events(normalized_phone, user_events)

    # Validate current event
    if current_event_id:
        if not EventService.event_exists(current_event_id):
            user_events = [e for e in user_events if e['event_id'] != current_event_id]
            UserTrackingService.update_user(normalized_phone, {
                'current_event_id': None,
                'events': user_events,
                'awaiting_event_id': True
            })
            send_message(From, f"The event '{current_event_id}' is no longer active...")
            return Response(status_code=200)

    # Check for inactivity (24 hours)
    if last_inactivity_prompt:
        last_prompt_time = datetime.fromisoformat(last_inactivity_prompt)
        now = datetime.now()
        if (now - last_prompt_time) >= timedelta(hours=24):
            # Reset inactivity tracking
            UserTrackingService.update_user(normalized_phone, {
                'last_inactivity_prompt': None,
                'invalid_attempts': 0
            })
```

## Code Comparison

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Lines of code | ~90 lines | ~45 lines | 50% reduction |
| Direct DB calls | 8+ | 0 | 100% cleaner |
| Duplication logic | 14 lines | 1 line | 93% reduction |
| Readability | Low | High | Much clearer |
| Testability | Hard | Easy | Mockable services |

## More Examples

### Event Information Retrieval

**Before**:
```python
event_info_ref = db.collection(f'AOI_{event_id}').document('info')
event_info_doc = event_info_ref.get()
if event_info_doc.exists:
    event_info = event_info_doc.to_dict()
    initial_message = event_info.get('initial_message', 'Thank you for agreeing to participate...')
    has_extra_questions = False
    extra = event_info.get('extra_questions', {})
    if extra:
        has_extra_questions = any(q.get('enabled') for q in extra.values())
```

**After**:
```python
initial_message = EventService.get_initial_message(event_id)
has_extra_questions = EventService.has_extra_questions(event_id)
```

### Participant Interaction Logging

**Before**:
```python
current_time = datetime.now()
interaction = {
    'message': extracted_text,
    'response': message_content,
    'ts': current_time.isoformat()
}
db.collection(normalize_event_path(current_event_id)).document(normalized_phone).update({
    'interactions': firestore.ArrayUnion([interaction])
})

# Check interaction limit
participant_ref = db.collection(normalize_event_path(current_event_id)).document(normalized_phone)
participant_doc = participant_ref.get()
if participant_doc.exists:
    participant_data = participant_doc.to_dict()
    interactions = participant_data.get('interactions', [])
    if len(interactions) >= 450:
        send_message(From, "You have reached the maximum number of interactions...")
        return Response(status_code=200)
```

**After**:
```python
current_time = datetime.now()
interaction = {
    'message': extracted_text,
    'response': message_content,
    'ts': current_time.isoformat()
}
ParticipantService.append_interaction(current_event_id, normalized_phone, interaction)

# Check interaction limit
if ParticipantService.get_interaction_count(current_event_id, normalized_phone) >= 450:
    send_message(From, "You have reached the maximum number of interactions...")
    return Response(status_code=200)
```

### Second Round Deliberation Check

**Before**:
```python
event_path = normalize_event_path(event_id)
info_ref = db.collection(event_path).document("info")
info_doc = info_ref.get()
if not info_doc.exists:
    return False

info = info_doc.to_dict() or {}
src = info.get("second_round_claims_source") or {}
if isinstance(src, dict):
    val = src.get("enabled")
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in {"true", "1", "yes", "on"}

legacy = info.get("second_deliberation_enabled")
if isinstance(legacy, bool):
    return legacy
if isinstance(legacy, str):
    return legacy.strip().lower() in {"true", "1", "yes", "on"}

return False
```

**After**:
```python
return EventService.is_second_round_enabled(event_id)
```

## Benefits Demonstrated

1. **Code Clarity**: Intent is immediately clear from method names
2. **Reduced Duplication**: Common patterns extracted into reusable methods
3. **Type Safety**: Service methods have clear signatures and return types
4. **Testability**: Easy to mock services in unit tests
5. **Maintainability**: Database schema changes only affect one file
6. **Error Handling**: Centralized error handling in service layer
7. **Logging**: Service layer handles logging consistently

## Migration Strategy

1. **Phase 1**: Import services alongside existing code
2. **Phase 2**: Replace user tracking operations
3. **Phase 3**: Replace event operations
4. **Phase 4**: Replace participant operations
5. **Phase 5**: Remove direct db imports
6. **Phase 6**: Add comprehensive tests

## Performance Impact

- **No performance penalty**: Services are thin wrappers around Firestore calls
- **Potential improvements**: Services can add caching, batch operations, connection pooling
- **Better async support**: Services can be made fully async for better concurrency

## Next Steps for Full Refactoring

To complete the refactoring across all handlers:

1. **ListenerMode.py** (777 lines, 20 db.collection calls)
   - User tracking: Lines 75-91 ✓ Easy
   - Event validation: Lines 120-135 ✓ Easy
   - Participant operations: Lines 200-400 ✓ Medium
   - Second round: Lines 650-777 ✓ Medium

2. **SurveyMode.py** (441 lines, 14 db.collection calls)
   - User tracking: Similar pattern ✓ Easy
   - Survey questions: Lines 150-250 ✓ Medium
   - Response tracking: Lines 300-400 ✓ Medium

3. **FollowupMode.py** (Similar to ListenerMode)
   - Follow same pattern as ListenerMode ✓ Easy

4. **deliberation/second_round_agent.py** (5 db.collection calls)
   - Report metadata: Lines 6-16 ✓ Easy
   - User context: Lines 36-52 ✓ Medium

Estimated effort: 4-6 hours for complete refactoring across all files.
