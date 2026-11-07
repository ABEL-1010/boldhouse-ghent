class ToolError(Exception):
    """A tool call failed in an expected way. The message is shown to the agent."""


class SandboxViolation(ToolError):
    """A tool call tried to reach outside the sandbox."""
