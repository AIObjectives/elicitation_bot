# Database Abstraction Layer Documentation

## Overview

The database abstraction layer provides a clean, type-safe interface for all Firestore operations in the WhatsApp bot. It encapsulates database logic into four main service classes:

1. **UserTrackingService** - User event tracking across conversations
2. **EventService** - Event configuration and metadata
3. **ParticipantService** - Participant data within events
4. **ReportService** - Report metadata for second round deliberation

## Benefits

- **Separation of Concerns**: Database logic separated from business logic
- **Type Safety**: Clear method signatures with type hints
- **Reusability**: Common operations encapsulated in reusable methods
- **Testability**: Easy to mock services for unit testing
- **Maintainability**: Changes to database structure centralized in one place
- **Documentation**: Self-documenting code with docstrings

## Service Classes

### UserTrackingService

Handles operations on the `user_event_tracking` collection.

#### Key Methods

```python
from app.services.firestore_service import UserTrackingService

# Get or create user tracking document
doc_ref, user_data = UserTrackingService.get_or_create_user(normalized_phone)

# Get user without creating
user_data = UserTrackingService.get_user(normalized_phone)

# Update user fields
UserTrackingService.update_user(normalized_phone, {
    'current_event_id': event_id,
    'awaiting_event_id': False
})

# Update events array
UserTrackingService.update_user_events(normalized_phone, events)

# Deduplicate events (keep most recent)
unique_events = UserTrackingService.deduplicate_events(events)

# Add or update event in events list
updated_events = UserTrackingService.add_or_update_event(
    events, event_id, timestamp=datetime.now()
)
```

### EventService

Handles operations on event collections (e.g., `AOI_event123`).

#### Key Methods

```python
from app.services.firestore_service import EventService

# Check if event exists
if EventService.event_exists(event_id):
    # Get full event info
    info = EventService.get_event_info(event_id)

    # Get specific fields
    mode = EventService.get_event_mode(event_id)
    initial_msg = EventService.get_initial_message(event_id)
    welcome_msg = EventService.get_welcome_message(event_id)
    completion_msg = EventService.get_completion_message(event_id)

    # Extra questions
    has_extra = EventService.has_extra_questions(event_id)
    questions, keys = EventService.get_ordered_extra_questions(event_id)

    # Survey questions
    survey_questions = EventService.get_survey_questions(event_id)

    # Second round deliberation
    is_enabled = EventService.is_second_round_enabled(event_id)
    config = EventService.get_second_round_config(event_id)
    prompts = EventService.get_second_round_prompts(event_id)
```

### ParticipantService

Handles participant documents within event collections.

#### Key Methods

```python
from app.services.firestore_service import ParticipantService

# Get participant data
participant = ParticipantService.get_participant(event_id, normalized_phone)

# Initialize participant if not exists
ParticipantService.initialize_participant(event_id, normalized_phone)

# Update participant fields
ParticipantService.update_participant(event_id, normalized_phone, {
    'extra_questions': {'name': 'John Doe'}
})

# Name operations
name = ParticipantService.get_participant_name(event_id, normalized_phone)
ParticipantService.set_participant_name(event_id, normalized_phone, 'Jane Smith')

# Interactions
ParticipantService.append_interaction(event_id, normalized_phone, {
    'message': 'User message',
    'response': 'Bot response',
    'ts': datetime.now().isoformat()
})

count = ParticipantService.get_interaction_count(event_id, normalized_phone)

# Second round interactions
ParticipantService.append_second_round_interaction(event_id, normalized_phone, {
    'message': 'Second round message',
    'ts': datetime.now().isoformat()
})

# Survey operations
is_complete = ParticipantService.is_survey_complete(event_id, normalized_phone)
progress = ParticipantService.get_survey_progress(event_id, normalized_phone)
# Returns: {'questions_asked': {}, 'responses': {}, 'last_question_id': None}

# Second round data
second_round = ParticipantService.get_second_round_data(event_id, normalized_phone)
# Returns: {'summary': ..., 'agreeable_claims': [], 'opposing_claims': [], ...}
```

### ReportService

Handles report collections for second round deliberation.

#### Key Methods

```python
from app.services.firestore_service import ReportService

# Get report metadata based on event config
metadata = ReportService.get_report_metadata(event_id)
```

## Migration Guide

### Before (Direct Firestore Access)

```python
# Old way - scattered database calls
user_tracking_ref = db.collection('user_event_tracking').document(normalized_phone)
user_tracking_doc = user_tracking_ref.get()
if user_tracking_doc.exists:
    user_data = user_tracking_doc.to_dict()
else:
    user_data = {
        'events': [],
        'current_event_id': None,
        'awaiting_event_id': False,
        # ... more fields
    }
    user_tracking_ref.set(user_data)

# Check event exists
event_info_ref = db.collection(f'AOI_{event_id}').document('info')
event_info_doc = event_info_ref.get()
if event_info_doc.exists:
    event_info = event_info_doc.to_dict()
    initial_message = event_info.get('initial_message', 'default...')

# Update participant
db.collection(f'AOI_{event_id}').document(normalized_phone).update({
    'interactions': firestore.ArrayUnion([interaction])
})
```

### After (Abstraction Layer)

```python
from app.services.firestore_service import (
    UserTrackingService, EventService, ParticipantService
)

# New way - clean service calls
doc_ref, user_data = UserTrackingService.get_or_create_user(normalized_phone)

# Check event exists
if EventService.event_exists(event_id):
    initial_message = EventService.get_initial_message(event_id)

# Update participant
ParticipantService.append_interaction(event_id, normalized_phone, interaction)
```

## Refactoring Example

### Original ListenerMode.py (Lines 75-91)

```python
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
```

### Refactored Version

```python
from app.services.firestore_service import UserTrackingService

# Step 1: Retrieve or initialize user tracking document
user_tracking_ref, user_data = UserTrackingService.get_or_create_user(normalized_phone)
```

**Result**: 16 lines reduced to 1 line, cleaner and more maintainable.

### Event Validation Example

**Before**:
```python
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
```

**After**:
```python
from app.services.firestore_service import UserTrackingService

# Remove duplicates in user_events
user_events = UserTrackingService.deduplicate_events(user_events)
UserTrackingService.update_user_events(normalized_phone, user_events)
```

## Testing

The abstraction layer makes testing much easier by allowing you to mock the service classes:

```python
from unittest.mock import patch, MagicMock

def test_my_handler():
    with patch('app.services.firestore_service.UserTrackingService') as mock_service:
        mock_service.get_or_create_user.return_value = (
            MagicMock(),
            {'events': [], 'current_event_id': None}
        )

        # Test your handler logic
        result = my_handler(...)

        # Verify service was called correctly
        mock_service.get_or_create_user.assert_called_once_with('1234567890')
```

## Next Steps

1. **Refactor Handlers**: Update ListenerMode, SurveyMode, and FollowupMode to use the abstraction layer
2. **Update Deliberation Module**: Refactor second_round_agent.py and related files
3. **Add Tests**: Write unit tests for the service classes
4. **Add Caching**: Consider adding caching for frequently accessed data (event info)
5. **Add Batch Operations**: For scenarios where multiple updates happen together

## Best Practices

1. **Always use the service layer** - Never call `db.collection()` directly in handlers
2. **Use type hints** - Leverage Python type hints for better IDE support
3. **Handle None gracefully** - Service methods return None when data doesn't exist
4. **Log appropriately** - Service layer already includes logging for key operations
5. **Keep services focused** - Each service class handles one collection type

## Performance Considerations

- **Caching**: Event info is read frequently but changes rarely - consider adding caching
- **Batch Operations**: The service layer could be extended to support batch reads/writes
- **Async Operations**: Consider making service methods async for better concurrency
- **Connection Pooling**: Firestore client already handles connection pooling

## Questions or Issues?

If you encounter issues or have questions about the database abstraction layer, please:
1. Check this documentation
2. Review the method docstrings in firestore_service.py
3. Look at refactored examples in the handlers
4. Create an issue in the repository
