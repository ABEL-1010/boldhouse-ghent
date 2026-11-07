import re

from sentinel.features.events import ToolName

OUTBOUND_TOOLS = frozenset({ToolName.SEND_EMAIL, ToolName.HTTP_POST})

# Paths and destinations that suggest credentials or secrets (Roadmap §5 Step 5).
SENSITIVE_TARGET = re.compile(r"(\.env|\.ssh|secret|credential|api[_-]?key|token|passw)", re.I)

# Common secret formats appearing in a payload.
SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9-]{16,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY)"
)
