import secrets


def new_session_id() -> str:
    """A session id in the event contract's `s_<alphanumeric>` format."""
    return f"s_{secrets.token_hex(4)}"
