from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.exceptions.domain import ConflictError, NotFoundError
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.badges.domain.badge_definitions import (
    BADGE_DEFINITIONS,
    BADGE_ORDER,
    LEVEL_1_BADGE,
    LEVEL_ORDER_TO_BADGE,
    POWER_USER_BADGE,
    BadgeDefinition,
)
from app.modules.badges.infrastructure.database.models import UserBadgeModel
from app.modules.badges.infrastructure.repositories.sqlalchemy_badge_repository import (
    SQLAlchemyBadgeRepository,
)
from app.modules.users.domain.entities.user import User

RL1_ACCOUNT_SUBSTITUTION_ID = "rl1-account-substitution"


@dataclass(slots=True)
class EarnBadgeResult:
    badge: UserBadgeModel
    created: bool


class EarnBadgeUseCase:
    def __init__(
        self,
        badges: SQLAlchemyBadgeRepository,
        analytics: SQLAlchemyAnalyticsRepository | None = None,
    ) -> None:
        self._badges = badges
        self._analytics = analytics

    async def execute(
        self,
        user: User,
        slug: str,
        *,
        metadata: dict | None = None,
    ) -> EarnBadgeResult:
        definition = _definition(slug)
        existing = await self._badges.get_for_user_slug(user.id, slug)
        if existing is not None:
            return EarnBadgeResult(existing, False)

        badge = await self._badges.create_badge(
            user_id=user.id,
            wallet_address=user.wallet_address,
            definition=definition,
            metadata=metadata or {},
            earned_at=datetime.now(UTC),
        )
        await self._record(
            "power_user_badge_earned" if slug == POWER_USER_BADGE else "badge_earned",
            user,
            definition,
        )
        return EarnBadgeResult(badge, True)

    async def _record(self, event_type: str, user: User, definition: BadgeDefinition) -> None:
        if self._analytics is None:
            return
        await self._analytics.record(
            event_type=event_type,
            user_id=user.id,
            wallet_address=user.wallet_address,
            subject_type="badge",
            subject_id=definition.slug,
            metadata={
                "badge_slug": definition.slug,
                "level_order": definition.level_order,
                "kind": definition.kind,
            },
        )


class EvaluateUserBadgesUseCase:
    def __init__(
        self,
        badges: SQLAlchemyBadgeRepository,
        analytics: SQLAlchemyAnalyticsRepository | None = None,
    ) -> None:
        self._badges = badges
        self._earn = EarnBadgeUseCase(badges, analytics)

    async def execute(self, user: User) -> list[EarnBadgeResult]:
        results: list[EarnBadgeResult] = []
        completed_orders = await self._badges.completed_level_orders(user.id)
        for order in sorted(completed_orders):
            slug = LEVEL_ORDER_TO_BADGE.get(order)
            if slug is not None:
                results.append(
                    await self._earn.execute(
                        user,
                        slug,
                        metadata={"source": "level_completion", "levelOrder": order},
                    )
                )

        if await self._badges.has_completed_research_lab(user.id, RL1_ACCOUNT_SUBSTITUTION_ID):
            results.append(
                await self._earn.execute(
                    user,
                    LEVEL_1_BADGE,
                    metadata={"source": "research_lab_completion", "labId": RL1_ACCOUNT_SUBSTITUTION_ID},
                )
            )
            results.append(
                await self._earn.execute(
                    user,
                    POWER_USER_BADGE,
                    metadata={
                        "source": "research_lab_certificate",
                        "labId": RL1_ACCOUNT_SUBSTITUTION_ID,
                    },
                )
            )
        return results

    async def earn_for_completed_level(self, user: User, level_order: int) -> list[EarnBadgeResult]:
        slug = LEVEL_ORDER_TO_BADGE.get(level_order)
        if slug is None:
            return []
        results = [
            await self._earn.execute(
                user,
                slug,
                metadata={"source": "level_completion", "levelOrder": level_order},
            )
        ]
        return results

    async def earn_for_research_lab_completion(self, user: User, lab_id: str) -> list[EarnBadgeResult]:
        if lab_id != RL1_ACCOUNT_SUBSTITUTION_ID:
            return []
        results = [
            await self._earn.execute(
                user,
                LEVEL_1_BADGE,
                metadata={"source": "research_lab_completion", "labId": lab_id},
            )
        ]
        results.append(
            await self._earn.execute(
                user,
                POWER_USER_BADGE,
                metadata={"source": "research_lab_certificate", "labId": lab_id},
            )
        )
        return results


class ListUserBadgesUseCase:
    def __init__(
        self,
        badges: SQLAlchemyBadgeRepository,
        analytics: SQLAlchemyAnalyticsRepository | None = None,
    ) -> None:
        self._badges = badges
        self._analytics = analytics

    async def execute(self, user: User) -> dict:
        await EvaluateUserBadgesUseCase(self._badges, self._analytics).execute(user)
        has_rl1_completion = await self._badges.has_completed_research_lab(
            user.id, RL1_ACCOUNT_SUBSTITUTION_ID
        )
        earned_by_slug = {badge.slug: badge for badge in await self._badges.list_for_user(user.id)}
        if not has_rl1_completion:
            earned_by_slug.pop(POWER_USER_BADGE, None)
        badges = [
            _badge_payload(definition, earned_by_slug.get(slug))
            for slug, definition in ((slug, BADGE_DEFINITIONS[slug]) for slug in BADGE_ORDER)
        ]
        earned_count = sum(1 for badge in badges if badge["earned"])
        return {
            "badges": badges,
            "summary": {
                "earned": earned_count,
                "total": len(BADGE_ORDER),
                "powerUserEarned": badges[-1]["earned"],
            },
        }


class MarkBadgeSeenUseCase:
    def __init__(
        self,
        badges: SQLAlchemyBadgeRepository,
        analytics: SQLAlchemyAnalyticsRepository | None = None,
    ) -> None:
        self._badges = badges
        self._analytics = analytics

    async def execute(self, user: User, slug: str) -> dict:
        _definition(slug)
        badge = await self._badges.get_for_user_slug(user.id, slug)
        if badge is None or not badge.earned:
            raise ConflictError("Badge has not been earned")
        if slug == POWER_USER_BADGE and not await self._badges.has_completed_research_lab(
            user.id, RL1_ACCOUNT_SUBSTITUTION_ID
        ):
            raise ConflictError("Badge has not been earned")
        if badge.seen_at is None:
            badge = await self._badges.update_seen_at(badge, datetime.now(UTC))
            if self._analytics is not None:
                await self._analytics.record(
                    event_type="badge_seen",
                    user_id=user.id,
                    wallet_address=user.wallet_address,
                    subject_type="badge",
                    subject_id=slug,
                    metadata={
                        "badge_slug": badge.slug,
                        "level_order": badge.level_order,
                        "kind": badge.kind,
                    },
                )
        return {"slug": badge.slug, "seenAt": _iso(badge.seen_at)}


def _definition(slug: str) -> BadgeDefinition:
    definition = BADGE_DEFINITIONS.get(slug)
    if definition is None:
        raise NotFoundError("Badge not found")
    return definition


def _badge_payload(definition: BadgeDefinition, badge: UserBadgeModel | None) -> dict:
    return {
        "slug": definition.slug,
        "title": definition.title,
        "description": definition.description,
        "kind": definition.kind,
        "levelOrder": definition.level_order,
        "image": definition.image,
        "earned": badge is not None and badge.earned,
        "earnedAt": _iso(badge.earned_at) if badge is not None else None,
        "seenAt": _iso(badge.seen_at) if badge is not None else None,
        "metadata": badge.metadata_json if badge is not None else {},
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None
