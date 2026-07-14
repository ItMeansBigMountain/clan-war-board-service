from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class ClanStanding:
    clan_id: str
    clan_name: str
    verified: bool
    completed_wars: int
    confirmed_wins: int
    agreed_draws: int
    disputed_results: int
    zone_control_minutes: int
    member_hours: float
    wom_group_id: int | None = None

    @property
    def score(self) -> float:
        # Conservative static leaderboard formula for early MVP.
        # Avoids pretending OSRS declares official wilderness winners.
        return round(
            (self.confirmed_wins * 100.0)
            + (self.agreed_draws * 25.0)
            + (self.zone_control_minutes * 0.2)
            + (self.member_hours * 0.5)
            - (self.disputed_results * 30.0),
            2,
        )

    def public_dict(self, rank: int) -> dict[str, Any]:
        data = asdict(self)
        data["rank"] = rank
        data["score"] = self.score
        # Keep identifiers useful, but never expose upcoming war intel here.
        return data


STATIC_STANDINGS: tuple[ClanStanding, ...] = (
    ClanStanding(
        clan_id="trapiistan",
        clan_name="TRAPISTAN",
        verified=False,
        completed_wars=0,
        confirmed_wins=0,
        agreed_draws=0,
        disputed_results=0,
        zone_control_minutes=0,
        member_hours=0.0,
        wom_group_id=None,
    ),
    ClanStanding(
        clan_id="example-rivals",
        clan_name="Example Rivals",
        verified=False,
        completed_wars=0,
        confirmed_wins=0,
        agreed_draws=0,
        disputed_results=0,
        zone_control_minutes=0,
        member_hours=0.0,
        wom_group_id=None,
    ),
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_clan_id(value: str) -> str:
    return "-".join(value.strip().lower().replace("_", "-").split())


def ranked_standings(standings: Iterable[ClanStanding] = STATIC_STANDINGS) -> list[dict[str, Any]]:
    ordered = sorted(
        standings,
        key=lambda row: (row.score, row.confirmed_wins, row.zone_control_minutes, row.member_hours, row.clan_name.lower()),
        reverse=True,
    )
    return [standing.public_dict(rank=index + 1) for index, standing in enumerate(ordered)]


def get_leaderboard() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "source": "static-mvp",
        "privacy": "completed-war summaries only; no upcoming world/time/hotspot intel",
        "standings": ranked_standings(),
    }


def get_clan(clan_id: str) -> dict[str, Any] | None:
    normalized = normalize_clan_id(clan_id)
    for clan in STATIC_STANDINGS:
        if clan.clan_id == normalized:
            return clan.public_dict(rank=rank_for_clan(normalized))
    return None


def rank_for_clan(clan_id: str) -> int:
    for row in ranked_standings():
        if row["clan_id"] == clan_id:
            return int(row["rank"])
    return 0


def get_public_availability() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "source": "static-mvp",
        "privacy": "public availability only; exact world/location/rally notes hidden",
        "availability": [
            {
                "id": "avail_static_trapistan_sunday",
                "creatorClanId": "trapiistan",
                "creatorClanName": "TRAPISTAN",
                "verificationStatus": "unverified",
                "status": "open",
                "timeWindow": "Sunday evening",
                "targetSize": "40v40-60v60",
                "warType": "wilderness_multi",
                "publicRulesSummary": "Returns allowed; multi fight",
            }
        ],
    }


def get_public_fight_summary(fight_id: str) -> dict[str, Any] | None:
    normalized = normalize_clan_id(fight_id)
    if normalized != "fight-static-example":
        return None
    return {
        "fightId": "fight-static-example",
        "status": "published",
        "privacy": "completed sanitized analytics only",
        "winnerClanId": "trapiistan",
        "winnerConfidence": "medium",
        "scoreExplanation": "Example completed-fight analytics; no upcoming intel is exposed.",
        "overview": {
            "durationMinutes": 60,
            "peakParticipants": 100,
            "thirdPartyInteractions": 0,
            "observedKills": 0,
            "observedDeaths": 0,
            "observedReturns": 0,
        },
        "byClan": [],
        "caveats": ["static_mvp_sample"],
    }


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "clan-war-board-service",
        "generatedAt": utc_now_iso(),
        "storage": "static-mvp",
    }


def wom_import_plan(group_id: int) -> dict[str, Any]:
    # Placeholder contract for later WOM Groups API integration.
    # We will import clan/group membership metadata only when the clan opts in.
    return {
        "womGroupId": group_id,
        "status": "planned",
        "source": "Wise Old Man Groups API",
        "allowedData": ["group name", "member list", "public WOM ranks/scores"],
        "excludedData": ["upcoming war world", "upcoming war hotspot", "private leader notes"],
    }
