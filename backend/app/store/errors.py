"""Repository errors (M0 §5.2)."""


class InquiryNotFound(Exception):
    def __init__(self, inquiry_id: str) -> None:
        super().__init__(inquiry_id)
        self.inquiry_id = inquiry_id


class TurnInProgress(Exception):
    pass


class VersionConflict(Exception):
    pass


class DuplicateReference(Exception):
    """Another inquiry already owns this reference (the column is unique in Postgres)."""

    def __init__(self, reference: str) -> None:
        super().__init__(reference)
        self.reference = reference
