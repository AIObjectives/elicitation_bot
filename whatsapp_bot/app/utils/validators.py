def is_valid_name(name: str) -> bool:
    """Checks if a name is non-empty, not 'Anonymous', and has at least one alphabetic character."""
    if not name:
        return False
    name = name.strip().strip('"').strip("'")
    if not name or name.lower() == "anonymous":
        return False
    return any(char.isalpha() for char in name)


def normalize_event_path(event_id: str) -> str:
    """
    Return event_id as-is for new schema (elicitation_bot_events).
    Legacy function maintained for backward compatibility.
    """
    return event_id

def normalize_phone(phone: str) -> str:
    """Normalize phone number by removing special characters."""
    return phone.replace("+", "").replace("-", "").replace(" ", "")

def _norm(s: str) -> str:
    """Collapse whitespace + lowercase to avoid trivial duplicates."""
    return " ".join((s or "").split()).strip().lower()