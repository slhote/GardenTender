from app.errors import InvalidInput


def normalize_name(value: str, label: str, max_len: int) -> str:
    """Collapses whitespace and enforces 1..max_len characters."""
    n = " ".join(value.split())
    if not 1 <= len(n) <= max_len:
        raise InvalidInput(f"{label} must be 1-{max_len} characters.")
    return n
