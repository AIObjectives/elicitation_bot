# # app/utils/validators.py


def is_valid_name(name: str) -> bool:
    """Checks if a name is non-empty, not 'Anonymous', and has at least one alphabetic character."""
    if not name:
        return False
    name = name.strip().strip('"').strip("'")
    if not name or name.lower() == "anonymous":
        return False
    return any(char.isalpha() for char in name)
