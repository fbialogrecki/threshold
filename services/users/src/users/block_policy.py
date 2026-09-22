"""Fresh canonical decisions; one SQL snapshot, no projection or allow cache."""

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session, aliased

from users.domain.models import ApplicationUser, UserBlock


def allowed_targets(session: Session, viewer_id: str, target_ids: list[str]) -> set[str]:
    """Only active identities without a block in either direction may interact.

    Request-scoped sessions read the primary database. Decisions begun after a
    block acknowledgement observe that commit; in-flight cross-database writes
    are not made atomic by this query.
    """
    viewer = aliased(ApplicationUser)
    active_viewer = exists().where(viewer.id == viewer_id, viewer.status == "active")
    blocked = exists().where(
        or_(
            and_(
                UserBlock.blocker_user_id == viewer_id,
                UserBlock.blocked_user_id == ApplicationUser.id,
            ),
            and_(
                UserBlock.blocked_user_id == viewer_id,
                UserBlock.blocker_user_id == ApplicationUser.id,
            ),
        )
    )
    return set(
        session.scalars(
            select(ApplicationUser.id).where(
                ApplicationUser.id.in_(target_ids),
                ApplicationUser.status == "active",
                active_viewer,
                ~blocked,
            )
        )
    )
