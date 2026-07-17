PAGE_FOLLOW_TARGET_TYPES = frozenset(
    {"page", "club", "collective", "project", "festival"}
)


def canonical_follow_target_type(target_type: str) -> str:
    return "page" if target_type in PAGE_FOLLOW_TARGET_TYPES else target_type
