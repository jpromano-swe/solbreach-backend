from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BadgeDefinition:
    slug: str
    title: str
    description: str
    image: str
    kind: str
    level_order: int | None = None


LEVEL_1_BADGE = "level-1-illusionist"
LEVEL_2_BADGE = "level-2-identity-thief"
LEVEL_3_BADGE = "level-3-trojan-horse"
POWER_USER_BADGE = "power-user"

CORE_LEVEL_BADGES = [LEVEL_1_BADGE, LEVEL_2_BADGE, LEVEL_3_BADGE]

BADGE_DEFINITIONS: dict[str, BadgeDefinition] = {
    LEVEL_1_BADGE: BadgeDefinition(
        slug=LEVEL_1_BADGE,
        level_order=1,
        title="The Illusionist",
        description="Earned by completing Level 1 or Research Lab 1.",
        image="/badges/badge-level-1.png",
        kind="level_badge",
    ),
    LEVEL_2_BADGE: BadgeDefinition(
        slug=LEVEL_2_BADGE,
        level_order=2,
        title="The Identity Thief",
        description="Earned by completing Level 2.",
        image="/badges/badge-level-2.png",
        kind="level_badge",
    ),
    LEVEL_3_BADGE: BadgeDefinition(
        slug=LEVEL_3_BADGE,
        level_order=3,
        title="The Trojan Horse",
        description="Earned by completing Level 3.",
        image="/badges/badge-level-3.png",
        kind="level_badge",
    ),
    POWER_USER_BADGE: BadgeDefinition(
        slug=POWER_USER_BADGE,
        title="Power User",
        description="Earned by collecting all core vulnerability badges.",
        image="/badges/badge-poweruser.png",
        kind="super_badge",
    ),
}

BADGE_ORDER = [LEVEL_1_BADGE, LEVEL_2_BADGE, LEVEL_3_BADGE, POWER_USER_BADGE]
LEVEL_ORDER_TO_BADGE = {
    definition.level_order: slug
    for slug, definition in BADGE_DEFINITIONS.items()
    if definition.level_order is not None
}
