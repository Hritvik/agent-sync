"""Custom exceptions for mcp-sync."""


class McpSyncError(Exception):
    """Base exception for mcp-sync errors."""

    pass


class ValidationError(McpSyncError):
    """Raised when configuration validation fails."""

    def __init__(self, message: str, server_name: str | None = None, field: str | None = None):
        self.server_name = server_name
        self.field = field
        super().__init__(message)


class ConflictError(McpSyncError):
    """Raised when a conflict is detected between existing and new configuration."""

    def __init__(
        self,
        message: str,
        server_name: str,
        client: str,
        existing_config: dict,
        new_config: dict,
    ):
        self.server_name = server_name
        self.client = client
        self.existing_config = existing_config
        self.new_config = new_config
        super().__init__(message)


class AdapterError(McpSyncError):
    """Raised when an adapter encounters an error."""

    def __init__(self, message: str, client: str):
        self.client = client
        super().__init__(message)


class BackupError(McpSyncError):
    """Raised when backup operations fail."""

    pass


class ConfigNotFoundError(McpSyncError):
    """Raised when a configuration file is not found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Configuration file not found: {path}")


class UnsupportedFeatureError(McpSyncError):
    """Raised when a client does not support a configured feature."""

    def __init__(self, message: str, client: str, feature: str):
        self.client = client
        self.feature = feature
        super().__init__(message)
