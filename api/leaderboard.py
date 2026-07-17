from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
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


def normalize_fight_terms(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        location = str(payload.get("location") or "").strip()
        world = int(payload.get("world"))
        starts_at = str(payload.get("startsAt") or "").strip()
        combat_min = int(payload.get("combatMin"))
        combat_max = int(payload.get("combatMax"))
        duration = int(payload.get("durationMinutes"))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid fight terms") from exc
    if not location or len(location) > 80 or not 301 <= world <= 599:
        raise ValueError("invalid location or OSRS world")
    try:
        parsed = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("startsAt must be ISO-8601") from exc
    if parsed.tzinfo is None or combat_min < 3 or combat_max > 126 or combat_min > combat_max or not 5 <= duration <= 180:
        raise ValueError("invalid time, combat range, or duration")
    rules = str(payload.get("rules") or "").strip()
    if len(rules) > 1000:
        raise ValueError("rules are too long")
    return {
        "location": location,
        "world": world,
        "startsAt": parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "combatMin": combat_min,
        "combatMax": combat_max,
        "durationMinutes": duration,
        "rules": rules,
    }


def terms_hash(terms: dict[str, Any]) -> str:
    canonical = json.dumps(terms, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def apply_challenge_action(challenge: dict[str, Any], action: str, clan_id: str, new_terms: dict[str, Any] | None = None) -> dict[str, Any]:
    result = json.loads(json.dumps(challenge))
    actor = normalize_clan_id(clan_id)
    if not actor:
        raise ValueError("clan identity is required")
    if action == "accept":
        accepted = list(dict.fromkeys([*result.get("acceptedBy", []), actor]))
        result["acceptedBy"] = accepted
        result["status"] = "confirmed" if len(accepted) >= 2 else "proposed"
    elif action == "counter":
        normalized = normalize_fight_terms(new_terms or {})
        result.update({"terms": normalized, "termsHash": terms_hash(normalized), "acceptedBy": [actor], "status": "reconfirm_required"})
    elif action in {"reject", "cancel"}:
        result["status"] = "rejected" if action == "reject" else "cancelled"
        result["acceptedBy"] = []
    else:
        raise ValueError("unsupported challenge action")
    result["updatedAt"] = utc_now_iso()
    return result


def storage_backend() -> str:
    return os.environ.get("STORAGE_BACKEND", "memory").strip().lower()


def cosmos_clans_container():
    if storage_backend() != "cosmos":
        return None
    endpoint = os.environ.get("COSMOS_ENDPOINT", "").strip()
    key = os.environ.get("COSMOS_KEY", "").strip()
    database = os.environ.get("COSMOS_DATABASE", "clan-war-board").strip()
    container = os.environ.get("COSMOS_CLANS_CONTAINER", "clans").strip()
    if not endpoint or not key:
        raise RuntimeError("Cosmos storage is selected but COSMOS_ENDPOINT/COSMOS_KEY are missing")
    from azure.cosmos import CosmosClient
    return CosmosClient(endpoint, credential=key).get_database_client(database).get_container_client(container)


def list_plugin_clans(limit: int = 100) -> list[dict[str, Any]]:
    container = cosmos_clans_container()
    if container is None:
        return list(PLUGIN_CLANS[:limit])
    query = "SELECT TOP @limit * FROM c WHERE c.docType = 'clan' ORDER BY c.updatedAt DESC"
    return list(container.query_items(query=query, parameters=[{"name": "@limit", "value": limit}], enable_cross_partition_query=True))


def load_plugin_clan(clan_id: str) -> dict[str, Any] | None:
    container = cosmos_clans_container()
    if container is None:
        return next((item for item in PLUGIN_CLANS if item.get("clan_id") == clan_id), None)
    try:
        return container.read_item(item=clan_id, partition_key=clan_id)
    except Exception as exc:
        if getattr(exc, "status_code", None) == 404:
            return None
        raise


def save_plugin_clan(row: dict[str, Any]) -> None:
    container = cosmos_clans_container()
    if container is None:
        current = next((item for item in PLUGIN_CLANS if item.get("clan_id") == row.get("clan_id")), None)
        if current is None:
            PLUGIN_CLANS.append(row)
        elif current is not row:
            current.clear()
            current.update(row)
        return
    document = dict(row)
    document["id"] = row["clan_id"]
    document["normalizedName"] = row["clan_id"]
    document["docType"] = "clan"
    container.upsert_item(document)


def register_plugin(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    install_id = str(payload.get("installId") or "").strip()
    clan_name = " ".join(str(payload.get("clanName") or "").strip().split())[:80]
    player_name = " ".join(str(payload.get("playerName") or "").strip().split())[:12]
    try:
        parsed_install_id = uuid.UUID(install_id)
        if parsed_install_id.version != 4:
            raise ValueError("install id must be UUIDv4")
    except (ValueError, AttributeError):
        return {"ok": False, "error": "invalid_install_id"}
    if not clan_name:
        return {"ok": False, "error": "clan_name_required"}

    clan_id = normalize_clan_id(clan_name)
    install_hash = hashlib.sha256(install_id.encode("utf-8")).hexdigest()
    now = utc_now_iso()
    row = load_plugin_clan(clan_id)
    if row is None:
        row = {
            "clan_id": clan_id,
            "clan_name": clan_name,
            "clan_type": "Unclassified",
            "registeredAt": now,
            "members": [],
        }

    members = row.setdefault("members", [])
    member = next((item for item in members if item.get("installHash") == install_hash), None)
    public_stats = bool(payload.get("publicStats", False))
    member_payload = {
        "installHash": install_hash,
        "displayName": player_name if public_stats and player_name else "Private member",
        "public": public_stats,
        "clanRank": int(payload.get("clanRank") or -1),
        "pluginVersion": str(payload.get("pluginVersion") or "unknown")[:32],
        "lastSeenAt": now,
    }
    if member is None:
        members.append(member_payload)
    else:
        member.clear()
        member.update(member_payload)
    row["member_count"] = len(members)
    row["updatedAt"] = now
    save_plugin_clan(row)
    return {
        "ok": True,
        "clanId": clan_id,
        "registeredMembers": row["member_count"],
        "publicStats": public_stats,
        "serverTime": now,
    }


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
    clans = [plugin_clan_profile(row, index + 1) for index, row in enumerate(list_plugin_clans(limit))]
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
    candidates = list_plugin_clans(100)
    direct = load_plugin_clan(normalized)
    if direct is not None and all(row.get("clan_id") != direct.get("clan_id") for row in candidates):
        candidates.append(direct)
    for row in candidates:
        profile = plugin_clan_profile(row)
        if normalize_clan_id(profile["clan_id"]) == normalized or normalize_clan_id(profile["clan_name"]) == normalized or normalize_clan_id(str(profile.get("clanChat") or "")) == normalized:
            profile["members"] = [
                {
                    "displayName": member.get("displayName") if member.get("public") else "Private member",
                    "public": bool(member.get("public", False)),
                    "lastSeenAt": member.get("lastSeenAt"),
                }
                for member in (row.get("members") or [])
            ]
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
        "storage": "cosmos" if storage_backend() == "cosmos" else "memory-local-only",
        "productionReadyStorage": storage_backend() == "cosmos",
    }
