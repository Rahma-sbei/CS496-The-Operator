class ToolError(Exception):
    """A failure whose message is safe and useful to show to the model."""


class GmailAuthError(Exception):
    """Gmail credentials are missing, expired or revoked."""
