from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class MemberSummary:
    role: str
    count: int
    plugin_seen: int


@dataclass(frozen=True)
class ClanStanding:
    clan_id: str
    clan_name: str
    verified: bool
    clan_type: str
    combat_bracket: str
    home_region: str
    description: str
    completed_wars: int
    confirmed_wins: int
    agreed_draws: int
    disputed_results: int
    zone_control_minutes: int
    member_hours: float
    member_count: int
    plugin_members_seen: int
    wom_group_id: int | None = None

    @property
    def score(self) -> float:
        return round(
            (self.confirmed_wins * 100.0)
            + (self.agreed_draws * 25.0)
            + (self.zone_control_minutes * 0.2)
            + (self.member_hours * 0.5)
            - (self.disputed_results * 30.0),
            2,
        )

    @property
    def win_rate(self) -> float:
        decided = self.confirmed_wins + self.agreed_draws + self.disputed_results
        if decided == 0:
            return 0.0
        return round((self.confirmed_wins / decided) * 100, 1)

    def public_dict(self, rank: int) -> dict[str, Any]:
        data = asdict(self)
        data["rank"] = rank
        data["score"] = self.score
        data["win_rate"] = self.win_rate
        return data


STATIC_STANDINGS: tuple[ClanStanding, ...] = (
    ClanStanding(
        clan_id="trapiistan",
        clan_name="TRAPISTAN",
        verified=False,
        clan_type="Main / Med Hybrid",
        combat_bracket="95-126 combat",
        home_region="Wilderness multi",
        description="Aggressive wilderness clan looking for structured Sunday multi fights.",
        completed_wars=4,
        confirmed_wins=3,
        agreed_draws=0,
        disputed_results=1,
        zone_control_minutes=146,
        member_hours=82.5,
        member_count=58,
        plugin_members_seen=37,
        wom_group_id=None,
    ),
    ClanStanding(
        clan_id="example-rivals",
        clan_name="Example Rivals",
        verified=False,
        clan_type="Pure Clan",
        combat_bracket="50-88 combat",
        home_region="Revenant Caves / Chaos Altar",
        description="Pure-focused clan seeking clean capped opts and return fights.",
        completed_wars=3,
        confirmed_wins=1,
        agreed_draws=1,
        disputed_results=0,
        zone_control_minutes=72,
        member_hours=48.0,
        member_count=41,
        plugin_members_seen=22,
        wom_group_id=12345,
    ),
    ClanStanding(
        clan_id="zerk-unit",
        clan_name="Zerk Unit",
        verified=True,
        clan_type="Zerker Clan",
        combat_bracket="75-105 combat",
        home_region="Lava Maze / Spider Hill",
        description="Zerker bracket squad built around short high-intensity capped fights.",
        completed_wars=5,
        confirmed_wins=3,
        agreed_draws=1,
        disputed_results=0,
        zone_control_minutes=111,
        member_hours=64.0,
        member_count=33,
        plugin_members_seen=28,
        wom_group_id=67890,
    ),
)

MEMBER_BREAKDOWNS: dict[str, list[MemberSummary]] = {
    "trapiistan": [MemberSummary("Leader", 3, 3), MemberSummary("Caller", 5, 4), MemberSummary("Member", 50, 30)],
    "example-rivals": [MemberSummary("Leader", 2, 2), MemberSummary("Caller", 4, 3), MemberSummary("Member", 35, 17)],
    "zerk-unit": [MemberSummary("Leader", 2, 2), MemberSummary("Caller", 3, 3), MemberSummary("Member", 28, 23)],
}

UPCOMING_BATTLES: list[dict[str, Any]] = [
    {
        "id": "avail_static_trapistan_sunday",
        "status": "open",
        "creatorClanId": "trapiistan",
        "creatorClanName": "TRAPISTAN",
        "creatorClanType": "Main / Med Hybrid",
        "verificationStatus": "unverified",
        "timeWindow": "Sunday evening",
        "scheduledTime": "2026-07-19T23:00:00Z",
        "durationMinutes": 60,
        "targetSize": "40v40-60v60",
        "warType": "wilderness_multi",
        "combatLevelRange": "95-126 combat",
        "publicLocation": "Wilderness multi zone",
        "publicWorldPolicy": "World revealed to accepted leaders and clan members only",
        "publicRulesSummary": "Returns allowed; multi fight; third-party interference tracked",
        "requiredAgreementFields": ["location", "world", "scheduledTime", "combatLevelRange", "durationMinutes"],
        "interestedClanIds": ["zerk-unit"],
    },
    {
        "id": "avail_static_rivals_pure_cap",
        "status": "open",
        "creatorClanId": "example-rivals",
        "creatorClanName": "Example Rivals",
        "creatorClanType": "Pure Clan",
        "verificationStatus": "unverified_wom_linked",
        "timeWindow": "Friday late EST",
        "scheduledTime": "2026-07-18T02:30:00Z",
        "durationMinutes": 45,
        "targetSize": "25v25-35v35",
        "warType": "pure_cap_return_fight",
        "combatLevelRange": "50-88 combat",
        "publicLocation": "Edgeville-to-deep-wild rotation",
        "publicWorldPolicy": "Exact world private until both leaders agree",
        "publicRulesSummary": "Pure bracket; matched opts; cap + return fight",
        "requiredAgreementFields": ["location", "world", "scheduledTime", "combatLevelRange", "durationMinutes"],
        "interestedClanIds": [],
    },
]

PAST_BATTLES: list[dict[str, Any]] = [
    {
        "fightId": "fight-static-example",
        "status": "published",
        "completedAt": "2026-07-12T00:05:00Z",
        "clans": ["trapiistan", "example-rivals"],
        "clanNames": ["TRAPISTAN", "Example Rivals"],
        "location": "Wilderness multi zone",
        "world": "private_after_completion",
        "durationMinutes": 60,
        "combatLevelRange": "95-126 combat",
        "winnerClanId": "trapiistan",
        "winnerClanName": "TRAPISTAN",
        "winnerConfidence": "medium",
        "overview": {
            "peakParticipants": 92,
            "observedKills": 38,
            "observedDeaths": 31,
            "observedReturns": 64,
            "thirdPartyInteractions": 7,
            "pluginClientsReporting": 48,
        },
        "byClan": [
            {"clanId": "trapiistan", "kills": 22, "deaths": 14, "returns": 37, "damageShare": 0.58},
            {"clanId": "example-rivals", "kills": 16, "deaths": 17, "returns": 27, "damageShare": 0.42},
        ],
        "caveats": ["static_mvp_sample", "winner confidence depends on plugin-client coverage"],
    }
]

FIGHT_SETUP_FIELDS: list[dict[str, str]] = [
    {"name": "opponentClanId", "label": "Opponent clan", "required": "true", "privacy": "leader"},
    {"name": "location", "label": "Fight location", "required": "true", "privacy": "leader/member after acceptance"},
    {"name": "world", "label": "OSRS world", "required": "true", "privacy": "leader/member after acceptance"},
    {"name": "scheduledTime", "label": "Scheduled start time", "required": "true", "privacy": "leader/member after acceptance"},
    {"name": "combatLevelRange", "label": "Combat level range", "required": "true", "privacy": "public summary"},
    {"name": "durationMinutes", "label": "Fight length", "required": "true", "privacy": "public summary"},
    {"name": "warType", "label": "Fight type", "required": "true", "privacy": "public summary"},
    {"name": "rules", "label": "Rules / returns / caps", "required": "true", "privacy": "public summary + private notes"},
]


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


def get_clans() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "source": "static-mvp",
        "clans": ranked_standings(),
    }


def get_clan(clan_id: str) -> dict[str, Any] | None:
    normalized = normalize_clan_id(clan_id)
    for clan in STATIC_STANDINGS:
        if clan.clan_id == normalized:
            public = clan.public_dict(rank=rank_for_clan(normalized))
            public["members"] = [asdict(row) for row in MEMBER_BREAKDOWNS.get(normalized, [])]
            public["wiseOldMan"] = wom_import_plan(clan.wom_group_id) if clan.wom_group_id else {"status": "not_linked"}
            public["upcomingBattles"] = [row for row in UPCOMING_BATTLES if row["creatorClanId"] == normalized or normalized in row.get("interestedClanIds", [])]
            public["pastBattles"] = [row for row in PAST_BATTLES if normalized in row["clans"]]
            return public
    return None


def search_clans(query: str) -> dict[str, Any]:
    normalized_query = query.strip().lower()
    results = []
    for clan in ranked_standings():
        haystack = " ".join(
            [clan["clan_id"], clan["clan_name"], clan["clan_type"], clan["combat_bracket"], clan.get("description", "")]
        ).lower()
        if not normalized_query or normalized_query in haystack:
            results.append(clan)
    return {"generatedAt": utc_now_iso(), "query": query, "results": results}


def rank_for_clan(clan_id: str) -> int:
    for row in ranked_standings():
        if row["clan_id"] == clan_id:
            return int(row["rank"])
    return 0


def get_public_availability() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "source": "static-mvp",
        "privacy": "public availability only; exact accepted world/rally notes hidden until agreement",
        "availability": UPCOMING_BATTLES,
        "fightSetupFields": FIGHT_SETUP_FIELDS,
    }


def get_past_battles() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "source": "static-mvp",
        "privacy": "completed sanitized analytics only",
        "battles": PAST_BATTLES,
    }


def get_public_fight_summary(fight_id: str) -> dict[str, Any] | None:
    normalized = normalize_clan_id(fight_id)
    for battle in PAST_BATTLES:
        if normalize_clan_id(battle["fightId"]) == normalized:
            summary = dict(battle)
            summary["privacy"] = "completed sanitized analytics only"
            summary["scoreExplanation"] = "Winner derived from kills, deaths, returns, presence, damage share, third-party noise, and client confidence."
            return summary
    return None


def get_fight_setup_schema() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "requiredFields": FIGHT_SETUP_FIELDS,
        "agreementModel": "Both leaders must accept the exact terms hash. Changes require reconfirmation.",
    }


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "clan-war-board-service",
        "generatedAt": utc_now_iso(),
        "storage": "static-mvp",
    }


def wom_import_plan(group_id: int | None) -> dict[str, Any]:
    if group_id is None:
        return {"status": "not_linked"}
    return {
        "womGroupId": group_id,
        "status": "linked_static_preview",
        "source": "Wise Old Man Groups API",
        "allowedData": ["group name", "member list", "public WOM ranks/scores"],
        "excludedData": ["upcoming war world", "upcoming war hotspot", "private leader notes"],
        "note": "Live Wise Old Man fetch is planned; current response is a static contract preview.",
    }
