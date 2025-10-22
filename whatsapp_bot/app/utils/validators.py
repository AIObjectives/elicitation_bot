def is_valid_name(name: str) -> bool:
    """Checks if a name is non-empty, not 'Anonymous', and has at least one alphabetic character."""
    if not name:
        return False
    name = name.strip().strip('"').strip("'")
    if not name or name.lower() == "anonymous":
        return False
    return any(char.isalpha() for char in name)


def normalize_event_path(event_id: str) -> str:
    """Ensure event_id always starts with 'AOI_' prefix."""
    return f"AOI_{event_id}" if not event_id.startswith("AOI_") else event_id
