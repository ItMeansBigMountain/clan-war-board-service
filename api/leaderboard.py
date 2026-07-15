from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from typing import Any

WOM_BASE_URL = "https://api.wiseoldman.net/v2"
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


def wom_url(path: str, **params: Any) -> str:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    return f"{WOM_BASE_URL}{path}" + (f"?{query}" if query else "")


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
            "inspiredBy": ["Old School RuneScape website", "Old School RuneScape Wiki theme"],
            "colors": {
                "parchment": "#e2dbc8",
                "bodyMid": "#d0bd97",
                "bodyBorder": "#94866d",
                "buttonDark": "#18140c",
                "osrsBrown": "#605443",
                "linkBrown": "#936039",
                "oldBrick": "#9f261e",
                "supernovaGold": "#f9d000",
            },
        },
        "images": images,
    }


def fetch_wom_groups(limit: int = 25) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    return cached_json(wom_url("/groups", limit=limit), ttl=CACHE_SECONDS)


def fetch_wom_group(group_id: int) -> dict[str, Any]:
    return cached_json(wom_url(f"/groups/{group_id}"), ttl=CACHE_SECONDS)


def infer_group_classification(group: dict[str, Any], memberships: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    text = " ".join(
        str(group.get(key) or "") for key in ["name", "clanChat", "description"]
    ).lower()
    if memberships:
        builds = Counter((m.get("player") or {}).get("build") or "unknown" for m in memberships)
        total = sum(builds.values()) or 1
        top_build, top_count = builds.most_common(1)[0]
        build_ratio = top_count / total
        if top_build == "pure" and build_ratio >= 0.35:
            return {"label": "Pure Clan", "source": "Wise Old Man member builds", "confidence": round(build_ratio, 2), "buildBreakdown": dict(builds)}
        if top_build in {"zerker", "berserker"} and build_ratio >= 0.25:
            return {"label": "Zerker Clan", "source": "Wise Old Man member builds", "confidence": round(build_ratio, 2), "buildBreakdown": dict(builds)}
        if top_build == "main" and build_ratio >= 0.45:
            return {"label": "Main Clan", "source": "Wise Old Man member builds", "confidence": round(build_ratio, 2), "buildBreakdown": dict(builds)}
    keyword_map = [
        ("pure", "Pure Clan"),
        ("zerk", "Zerker Clan"),
        ("pvp", "PvP Clan"),
        ("pk", "PvP Clan"),
        ("wild", "Wilderness Clan"),
        ("iron", "Ironman Clan"),
        ("pvm", "PvM Clan"),
        ("social", "Social Clan"),
    ]
    for token, label in keyword_map:
        if token in text:
            return {"label": label, "source": "Wise Old Man group text", "confidence": 0.55, "buildBreakdown": {}}
    return {"label": "OSRS Clan", "source": "Wise Old Man group listing", "confidence": 0.35, "buildBreakdown": {}}


def public_group(group: dict[str, Any], rank: int | None = None, include_members: bool = False) -> dict[str, Any]:
    memberships = group.get("memberships") if include_members else None
    classification = infer_group_classification(group, memberships)
    members = []
    role_counts: dict[str, int] = {}
    if include_members and memberships:
        for membership in memberships:
            role = membership.get("role") or "member"
            role_counts[role] = role_counts.get(role, 0) + 1
        for membership in memberships[:100]:
            player = membership.get("player") or {}
            members.append(
                {
                    "displayName": player.get("displayName") or player.get("username"),
                    "role": membership.get("role"),
                    "type": player.get("type"),
                    "build": player.get("build"),
                    "status": player.get("status"),
                    "country": player.get("country"),
                    "ehp": player.get("ehp"),
                    "ehb": player.get("ehb"),
                    "updatedAt": player.get("updatedAt"),
                }
            )
    payload = {
        "clan_id": str(group.get("id")),
        "womGroupId": group.get("id"),
        "clan_name": group.get("name"),
        "clanChat": group.get("clanChat"),
        "description": group.get("description"),
        "homeworld": group.get("homeworld"),
        "verified": group.get("verified"),
        "patron": group.get("patron"),
        "visible": group.get("visible"),
        "profileImage": group.get("profileImage"),
        "bannerImage": group.get("bannerImage"),
        "womScore": group.get("score"),
        "member_count": group.get("memberCount") or len(members),
        "updatedAt": group.get("updatedAt"),
        "clan_type": classification["label"],
        "classification": classification,
        "dataSource": "Wise Old Man Groups API",
    }
    if rank is not None:
        payload["rank"] = rank
    if include_members:
        payload["members"] = members
        payload["roleCounts"] = role_counts
        payload["wiseOldMan"] = wom_import_plan(group.get("id"))
    return payload


def get_clans(limit: int = 25) -> dict[str, Any]:
    try:
        groups = fetch_wom_groups(limit=limit)
        clans = [public_group(group, rank=index + 1) for index, group in enumerate(groups)]
        return {"generatedAt": utc_now_iso(), "source": "Wise Old Man Groups API", "clans": clans}
    except Exception as exc:
        return {"generatedAt": utc_now_iso(), "source": "Wise Old Man Groups API", "error": "wom_unavailable", "detail": str(exc), "clans": []}


def get_leaderboard() -> dict[str, Any]:
    payload = get_clans(limit=25)
    payload["privacy"] = "real Wise Old Man group listing; no Clan War Board scheduled-fight intel"
    payload["standings"] = payload.pop("clans")
    return payload


def search_clans(query: str) -> dict[str, Any]:
    payload = get_clans(limit=100)
    q = query.strip().lower()
    results = []
    for clan in payload.get("clans", []):
        haystack = " ".join(
            str(clan.get(key) or "") for key in ["clan_id", "clan_name", "clanChat", "description", "clan_type"]
        ).lower()
        if not q or q in haystack:
            results.append(clan)
    return {"generatedAt": utc_now_iso(), "source": payload.get("source"), "query": query, "results": results}


def get_clan(clan_id: str) -> dict[str, Any] | None:
    normalized = normalize_clan_id(clan_id)
    group_id = int(clan_id) if clan_id.isdigit() else None
    if group_id is None:
        for group in fetch_wom_groups(limit=100):
            if normalize_clan_id(str(group.get("name") or "")) == normalized or normalize_clan_id(str(group.get("clanChat") or "")) == normalized:
                group_id = int(group["id"])
                break
    if group_id is None:
        return None
    group = fetch_wom_group(group_id)
    profile = public_group(group, include_members=True)
    profile["upcomingBattles"] = []
    profile["pastBattles"] = []
    profile["clanWarBoardData"] = {
        "status": "no_plugin_scheduled_fights_yet",
        "message": "Real fight posts will appear after RuneLite leader write endpoints are enabled and clans submit matches.",
    }
    return profile


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


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "clan-war-board-service",
        "generatedAt": utc_now_iso(),
        "storage": "wom-live-staticwebapp-managed-api",
    }


def wom_import_plan(group_id: int | None) -> dict[str, Any]:
    if group_id is None:
        return {"status": "not_linked"}
    return {
        "womGroupId": group_id,
        "status": "linked_live",
        "source": "Wise Old Man Groups API",
        "allowedData": ["group name", "member list", "public WOM ranks/scores", "player build/type/status"],
        "excludedData": ["upcoming war world", "upcoming war hotspot", "private leader notes"],
    }
