"""Service-layer errors."""


class ServiceError(Exception):
    """Base class for service errors."""


class ReferenceNotFoundError(ServiceError):
    """Submitted reference is unknown."""


class UploadTooLargeError(ServiceError):
    """Upload exceeded the configured size limit."""


class UploadValidationError(ServiceError):
    """Upload failed validation (extension or size)."""
