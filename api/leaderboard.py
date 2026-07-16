from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

WIKI_API_URL = "https://oldschool.runescape.wiki/api.php"
USER_AGENT = "ClanWarBoard/0.2 (+https://github.com/ItMeansBigMountain/clan-war-board-service)"
CACHE_SECONDS = 300
_CACHE: dict[str, tuple[float, Any]] = {}

OSRS_IMAGE_PAGES = ("Wilderness", "Clan Wars", "Revenant Caves")

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


def cached_json(url: str, ttl: int = CACHE_SECONDS) -> Any:
    now = time.time()
    cached = _CACHE.get(url)
    if cached and now - cached[0] < ttl:
        return cached[1]
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as response:
        payload = json.load(response)
    _CACHE[url] = (now, payload)
    return payload


def wiki_image_url(page: str, size: int = 1000) -> str | None:
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "piprop": "thumbnail|original",
        "pithumbsize": size,
        "titles": page,
        "origin": "*",
    }
    try:
        data = cached_json(f"{WIKI_API_URL}?{urllib.parse.urlencode(params)}", ttl=86400)
        pages = data.get("query", {}).get("pages", {})
        for row in pages.values():
            thumb = row.get("thumbnail") or row.get("original") or {}
            if thumb.get("source"):
                return thumb["source"]
    except Exception:
        return None
    return None


def get_theme_assets() -> dict[str, Any]:
    images = []
    for page in OSRS_IMAGE_PAGES:
        source = wiki_image_url(page)
        if source:
            images.append({"title": page, "source": source, "attribution": "Old School RuneScape Wiki"})
    return {
        "generatedAt": utc_now_iso(),
        "source": "OSRS Wiki MediaWiki API",
        "theme": {
            "inspiredBy": ["burned Wilderness forest", "stone castle walls", "Old School RuneScape website", "Old School RuneScape Wiki theme"],
            "colors": {
                "charcoal": "#120f0c",
                "burntForest": "#1d2116",
                "stone": "#4d4a43",
                "darkParchment": "#c7b28c",
                "bodyBorder": "#6f6658",
                "ember": "#a83b22",
                "ashGold": "#d7aa35",
            },
        },
        "images": images,
    }


PLUGIN_CLANS: list[dict[str, Any]] = []

def plugin_clan_profile(row: dict[str, Any], rank: int | None = None) -> dict[str, Any]:
    member_count = int(row.get("member_count") or row.get("memberCount") or 0)
    wins = int(row.get("wins") or 0)
    losses = int(row.get("losses") or 0)
    draws = int(row.get("draws") or 0)
    battles = int(row.get("battles") or wins + losses + draws)
    payload = {
        "clan_id": str(row.get("clan_id") or normalize_clan_id(str(row.get("clan_name") or row.get("clanName") or "unknown"))),
        "clan_name": row.get("clan_name") or row.get("clanName") or "Unknown clan",
        "clanChat": row.get("clanChat") or row.get("clan_name") or row.get("clanName"),
        "description": row.get("description") or "Registered through Clan War Board plugin activity.",
        "homeworld": row.get("homeworld"),
        "verified": bool(row.get("verified", False)),
        "profileImage": row.get("profileImage"),
        "bannerImage": row.get("bannerImage"),
        "member_count": member_count,
        "updatedAt": row.get("updatedAt") or utc_now_iso(),
        "clan_type": row.get("clan_type") or row.get("clanType") or "Plugin Clan",
        "classification": {
            "label": row.get("clan_type") or row.get("clanType") or "Plugin Clan",
            "source": "Clan War Board plugin registration",
            "confidence": 1.0 if row.get("clan_type") or row.get("clanType") else 0.5,
            "buildBreakdown": row.get("buildBreakdown") or {},
        },
        "dataSource": "Clan War Board plugin",
        "stats": {
            "battles": battles,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "kills": int(row.get("kills") or 0),
            "deaths": int(row.get("deaths") or 0),
            "returns": int(row.get("returns") or 0),
            "damageDealt": int(row.get("damageDealt") or 0),
            "damageTaken": int(row.get("damageTaken") or 0),
        },
    }
    if rank is not None:
        payload["rank"] = rank
    return payload

def get_clans(limit: int = 25) -> dict[str, Any]:
    clans = [plugin_clan_profile(row, index + 1) for index, row in enumerate(PLUGIN_CLANS[:limit])]
    return {
        "generatedAt": utc_now_iso(),
        "source": "Clan War Board plugin",
        "registrationPolicy": "Only clans seen through the RuneLite plugin or leader registration appear here.",
        "clans": clans,
        "emptyState": "No clans have registered through the Clan War Board plugin yet.",
    }

def get_leaderboard() -> dict[str, Any]:
    payload = get_clans(limit=25)
    payload["privacy"] = "plugin-registered clans only; no external clan-directory promotion"
    payload["standings"] = payload.pop("clans")
    return payload

def search_clans(query: str) -> dict[str, Any]:
    payload = get_clans(limit=100)
    q = query.strip().lower()
    results = []
    for clan in payload.get("clans", []):
        haystack = " ".join(str(clan.get(key) or "") for key in ["clan_id", "clan_name", "clanChat", "description", "clan_type"]).lower()
        if not q or q in haystack:
            results.append(clan)
    return {"generatedAt": utc_now_iso(), "source": payload.get("source"), "query": query, "results": results, "emptyState": payload.get("emptyState")}

def get_clan(clan_id: str) -> dict[str, Any] | None:
    normalized = normalize_clan_id(clan_id)
    for row in PLUGIN_CLANS:
        profile = plugin_clan_profile(row)
        if normalize_clan_id(profile["clan_id"]) == normalized or normalize_clan_id(profile["clan_name"]) == normalized or normalize_clan_id(str(profile.get("clanChat") or "")) == normalized:
            profile["members"] = row.get("members") or []
            profile["roleCounts"] = row.get("roleCounts") or {}
            profile["upcomingBattles"] = row.get("upcomingBattles") or []
            profile["pastBattles"] = row.get("pastBattles") or []
            profile["clanWarBoardData"] = {
                "status": "plugin_registered",
                "message": "In-depth clan pages are based on Clan War Board fight history, member telemetry, and published stats.",
            }
            return profile
    return None

def get_public_availability() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "source": "Clan War Board plugin submissions",
        "privacy": "public availability only; exact accepted world/rally notes hidden until agreement",
        "availability": [],
        "emptyState": "No real scheduled fights have been posted yet. The next step is enabling authenticated RuneLite leader submissions.",
        "fightSetupFields": FIGHT_SETUP_FIELDS,
    }


def get_past_battles() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "source": "Clan War Board completed fight telemetry",
        "privacy": "completed sanitized analytics only",
        "battles": [],
        "emptyState": "No real completed Clan War Board fights have been published yet.",
    }


def get_public_fight_summary(fight_id: str) -> dict[str, Any] | None:
    return None


def get_fight_setup_schema() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "requiredFields": FIGHT_SETUP_FIELDS,
        "agreementModel": "Both leaders must accept the exact terms hash. Changes require reconfirmation.",
    }



def get_win_judging_system() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "system": "terms_locked_weighted_score",
        "summary": "Clan War Board should determine winners from the accepted fight terms plus plugin telemetry collected during the scheduled window.",
        "requiredBeforeFight": [
            "both leaders accept the same terms hash",
            "scheduled start and end time are locked",
            "fight location and world are locked privately",
            "combat bracket and allowed return rules are locked",
        ],
        "winnerSignals": [
            {"name": "kills", "weight": 35, "description": "confirmed kills by participating clan members during the agreed window"},
            {"name": "deaths", "weight": -20, "description": "confirmed deaths by participating clan members during the agreed window"},
            {"name": "returns", "weight": 15, "description": "members returning to the fight after death or bank trips when returns are allowed"},
            {"name": "durationControl", "weight": 15, "description": "which clan maintained more active members near the agreed location over time"},
            {"name": "damagePressure", "weight": 10, "description": "damage dealt versus taken among participating members"},
            {"name": "thirdPartyAdjustment", "weight": 5, "description": "reduces confidence when outside clans or unaffiliated players heavily interfere"},
        ],
        "outcomes": [
            "win",
            "loss",
            "draw",
            "disputed",
            "no contest",
        ],
        "confidenceRules": [
            "high confidence requires both clans to have enough plugin participants online",
            "heavy third-party damage lowers confidence",
            "missing leader confirmation can mark the result disputed",
            "fight ending early by mutual agreement can publish a no-contest or agreed winner",
        ],
        "publicLeaderboardPolicy": "Only completed, non-disputed fights with enough confidence should affect leaderboard rating.",
    }

def get_challenge_system() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "leaderActions": [
            {"name": "Open challenge", "description": "Post availability for any suitable clan to request."},
            {"name": "Direct challenge", "description": "Choose a specific clan and propose time, world, location, combat range, duration, and rules."},
            {"name": "Counter offer", "description": "Respond with a different time/world/rules while keeping the same opponent."},
            {"name": "Accept terms", "description": "Lock both leaders to the same terms hash before members see private rally details."},
        ],
        "directChallengeRequiredFields": FIGHT_SETUP_FIELDS,
        "privateUntilAccepted": ["world", "exact rally location", "leader notes"],
    }

def get_competitive_leaderboard() -> dict[str, Any]:
    base = get_leaderboard()
    standings = []
    for index, clan in enumerate(base.get("standings", []), start=1):
        standings.append({
            "rank": index,
            "clan_id": clan.get("clan_id"),
            "clan_name": clan.get("clan_name"),
            "clan_type": clan.get("clan_type"),
            "member_count": clan.get("member_count"),
            "rating": None,
            "record": {"wins": 0, "losses": 0, "draws": 0, "disputed": 0},
            "ratingStatus": "unrated_until_completed_clan_war_board_fights",
        })
    return {
        "generatedAt": utc_now_iso(),
        "source": "Clan War Board plugin completed fight results",
        "leaderboardPolicy": get_win_judging_system()["publicLeaderboardPolicy"],
        "standings": standings,
    }

def submit_telemetry_batch(payload: dict[str, Any] | None, client_headers: dict[str, str] | None = None) -> dict[str, Any]:
    payload = payload or {}
    events = payload.get("events") if isinstance(payload, dict) else []
    if not isinstance(events, list):
        return {"ok": False, "error": "events_must_be_array", "accepted": 0}
    max_batch = 50
    accepted_events = []
    for event in events[:max_batch]:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "")
        if event_type not in {"heartbeat", "damage_dealt", "damage_taken", "death", "kill_candidate", "return", "location_sample", "third_party_damage"}:
            continue
        accepted_events.append(
            {
                "type": event_type,
                "playerPublic": bool(event.get("playerPublic", False)),
                "publicPlayerName": event.get("playerName") if bool(event.get("playerPublic", False)) else None,
                "clanName": event.get("clanName"),
                "opponentName": event.get("opponentName"),
                "amount": int(event.get("amount") or 0),
                "world": int(event.get("world") or 0),
                "tick": int(event.get("tick") or 0),
                "timestamp": int(event.get("timestamp") or 0),
            }
        )
    return {
        "ok": True,
        "accepted": len(accepted_events),
        "rejected": max(0, len(events) - len(accepted_events)),
        "maxBatch": max_batch,
        "policy": {
            "worldIsPublic": True,
            "playerWebsiteTrackingDefaultsPrivate": True,
            "recommendedClientFlushSeconds": 10,
            "recommendedMaxEventsPerBatch": 50,
            "notes": "The server accepts batched telemetry so large wars do not generate one API request per visible player or per frame.",
        },
        "stored": "ephemeral-validation-only-until-cosmos-ingestion-is-enabled",
    }


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "clan-war-board-service",
        "generatedAt": utc_now_iso(),
        "storage": "plugin-registered-staticwebapp-managed-api",
    }
