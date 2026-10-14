"""Shared predicates for live eval scripts (not used in production graph)."""


def off_topic_offers_continue(text: str) -> bool:
    """True when a decline still invites the user back to the leasing flow."""
    lowered = text.lower()
    if any(
        phrase in lowered
        for phrase in (
            "continue",
            "carry on",
            "get started",
            "take it from there",
        )
    ):
        return True
    if "help" in lowered and ("send" in lowered or "lease" in lowered):
        return True
    if "tell me" in lowered and any(w in lowered for w in ("brand", "lease", "open")):
        return True
    if ("inquiry" in lowered or "inquiries" in lowered) and any(
        phrase in lowered
        for phrase in (
            "tell me",
            "send me",
            "if you",
            "if you're",
            "i can help",
            "happy to",
            "we can",
            "i'll take",
        )
    ):
        return True
    return False
