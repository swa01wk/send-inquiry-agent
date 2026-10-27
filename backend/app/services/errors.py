"""Service-layer errors."""


class ServiceError(Exception):
    """Base class for service errors."""


class ReferenceNotFoundError(ServiceError):
    """Submitted reference is unknown."""


class UploadTooLargeError(ServiceError):
    """Upload exceeded the configured size limit."""


class UploadValidationError(ServiceError):
    """Upload failed validation (extension or size)."""


class ServiceTimeout(ServiceError):
    """The external system didn't answer in time."""


class ServiceUnavailable(ServiceError):
    """The external system is down or refused the connection."""


class ServiceRejected(ServiceError):
    """The external system answered with a definite no (e.g. a validation failure)."""
