from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

WIKI_API_URL = "https://oldschool.runescape.wiki/api.php"
USER_AGENT = "ClanWarBoard/0.2 (+https://github.com/ItMeansBigMountain/clan-war-board-service)"
CACHE_SECONDS = 300
_CACHE: dict[str, tuple[float, Any]] = {}

OSRS_IMAGE_PAGES = ("Wilderness", "Clan Wars", "Revenant Caves")

FIGHT_MODES = {
    "cwa": {
        "label": "Clan Wars Arena",
        "shortLabel": "CWA",
        "primary": True,
        "returnsAllowed": False,
        "rankingSignals": ["result", "damagePressure", "tankEfficiency", "offPrayerAccuracy", "binding", "pileParticipation", "survival"],
    },
    "wildy": {
        "label": "Wilderness",
        "shortLabel": "Wildy",
        "primary": False,
        "returnsAllowed": True,
        "rankingSignals": ["result", "kills", "deaths", "returns", "durationControl", "damagePressure", "thirdPartyAdjustment"],
    },
}

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
INSTALL_SESSIONS: dict[str, dict[str, Any]] = {}
AVAILABILITY: list[dict[str, Any]] = []
CHALLENGES: list[dict[str, Any]] = []
TELEMETRY_EVENTS: list[dict[str, Any]] = []
RATING_AUDIT_RECORDS: list[dict[str, Any]] = []
MODERATION_AUDIT_RECORDS: list[dict[str, Any]] = []
SESSION_SECONDS = 3600
WRITE_CLOCK_SKEW_SECONDS = 300
WRITE_RATE_LIMIT = 30
LEADER_RANK_MINIMUM = 100
RATING_SCHEMA_VERSION = "rating.v1"
RATING_START = 1000
RATING_K_FACTOR = 32
RATING_MIN_ROSTER_MEMBERS = 2
RATING_ACCEPTED_CONFIDENCE = {"high", "verified"}


def _install_hash(install_id: str) -> str:
    return hashlib.sha256(install_id.encode("utf-8")).hexdigest()


def _player_hash(clan_id: str, player_name: str) -> str:
    player_key = " ".join(str(player_name or "").strip().split()).lower()
    return hashlib.sha256((normalize_clan_id(clan_id) + "\0" + player_key).encode("utf-8")).hexdigest()


def _roster_snapshot(members: Any, clan_id: str) -> dict[str, Any]:
    names = []
    if isinstance(members, list):
        for value in members[:500]:
            name = str(value.get("displayName") or value.get("playerName") or value.get("name") or "") if isinstance(value, dict) else str(value or "")
            normalized = " ".join(name.strip().split())[:12]
            if normalized:
                names.append(normalized)
    hashes = sorted(set(_player_hash(clan_id, name) for name in names))
    return {"schemaVersion": "roster.v1", "memberCount": len(hashes), "playerHashes": hashes, "capturedAt": utc_now_iso()}


def grant_verified_leader(clan_name: str, install_id: str) -> None:
    """Server-side/admin helper: mark an installation as authoritative for leader writes."""
    clan_id = normalize_clan_id(clan_name)
    row = load_plugin_clan(clan_id) or {"clan_id": clan_id, "clan_name": clan_name, "clan_type": "Unclassified", "members": []}
    hashes = set(row.get("verifiedLeaderInstallHashes") or [])
    hashes.add(_install_hash(install_id))
    row["verifiedLeaderInstallHashes"] = sorted(hashes)
    row["updatedAt"] = utc_now_iso()
    save_plugin_clan(row)


def grant_verified_moderator(clan_name: str, install_id: str) -> None:
    """Server-side helper; moderator authority is never accepted from a client claim."""
    clan_id = normalize_clan_id(clan_name)
    row = load_plugin_clan(clan_id) or {"clan_id": clan_id, "clan_name": clan_name, "members": []}
    hashes = set(row.get("verifiedModeratorInstallHashes") or [])
    hashes.add(_install_hash(install_id))
    row["verifiedModeratorInstallHashes"] = sorted(hashes)
    row["updatedAt"] = utc_now_iso()
    save_plugin_clan(row)


def _is_verified_leader(clan: dict[str, Any], install_hash: str) -> bool:
    return install_hash in set(clan.get("verifiedLeaderInstallHashes") or [])


def _is_verified_moderator(clan: dict[str, Any], install_hash: str) -> bool:
    return install_hash in set(clan.get("verifiedModeratorInstallHashes") or [])


def classify_participant(fight: dict[str, Any], reporting_clan_id: str, player_name: str) -> str:
    reporting = normalize_clan_id(reporting_clan_id)
    player_hash = _player_hash(reporting, player_name)
    snapshots = fight.get("acceptedRosterSnapshots") if isinstance(fight.get("acceptedRosterSnapshots"), dict) else {}
    own = snapshots.get(reporting) if isinstance(snapshots, dict) else None
    if isinstance(own, dict) and player_hash in set(own.get("playerHashes") or []):
        return "accepted_own_roster"
    for clan_id, snapshot in snapshots.items() if isinstance(snapshots, dict) else []:
        if clan_id == reporting or not isinstance(snapshot, dict):
            continue
        if _player_hash(str(clan_id), player_name) in set(snapshot.get("playerHashes") or []):
            return "accepted_rival_roster"
    return "outsider"


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
    mode = str(payload.get("mode") or "cwa").strip().lower()
    if mode not in FIGHT_MODES:
        raise ValueError("mode must be cwa or wildy")
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
        "mode": mode,
        "returnsAllowed": mode == "wildy" and bool(payload.get("returnsAllowed", True)),
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
        result.update({"terms": normalized, "termsHash": terms_hash(normalized), "acceptedBy": [actor], "status": "reconfirm_required", "acceptedRosterSnapshots": {}})
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


def cosmos_wars_container():
    if storage_backend() != "cosmos":
        return None
    endpoint = os.environ.get("COSMOS_ENDPOINT", "").strip()
    key = os.environ.get("COSMOS_KEY", "").strip()
    database = os.environ.get("COSMOS_DATABASE", "clan-war-board").strip()
    container = os.environ.get("COSMOS_WARS_CONTAINER", "wars").strip()
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


def _save_session(session: dict[str, Any]) -> None:
    container = cosmos_clans_container()
    if container is not None:
        document = dict(session)
        document["normalizedName"] = session["id"]
        if session.get("_etag"):
            from azure.core import MatchConditions
            saved = container.replace_item(
                item=session["id"],
                body=document,
                etag=session["_etag"],
                match_condition=MatchConditions.IfNotModified,
            )
        else:
            saved = container.upsert_item(document)
        session.clear()
        session.update(saved)
    INSTALL_SESSIONS[session["id"]] = session


def _load_session(session_id: str) -> dict[str, Any] | None:
    cached = INSTALL_SESSIONS.get(session_id)
    if cached is not None:
        return cached
    container = cosmos_clans_container()
    if container is None:
        return None
    try:
        session = container.read_item(item=session_id, partition_key=session_id)
    except Exception as exc:
        if getattr(exc, "status_code", None) == 404:
            return None
        raise
    if session.get("docType") != "installationSession":
        return None
    INSTALL_SESSIONS[session_id] = session
    return session


def _revoke_installation_sessions(install_hash: str, now: int | None = None) -> None:
    revoked_at = int(time.time() if now is None else now)
    sessions = [row for row in INSTALL_SESSIONS.values() if row.get("installHash") == install_hash and not row.get("revokedAtEpoch")]
    container = cosmos_clans_container()
    if container is not None:
        persisted = container.query_items(
            query="SELECT * FROM c WHERE c.docType = 'installationSession' AND c.installHash = @install AND NOT IS_DEFINED(c.revokedAtEpoch)",
            parameters=[{"name": "@install", "value": install_hash}],
            enable_cross_partition_query=True,
        )
        known = {str(row.get("id")) for row in sessions}
        sessions.extend(row for row in persisted if str(row.get("id")) not in known)
    for session in sessions:
        session["revokedAtEpoch"] = revoked_at
        _save_session(session)


def _save_war_document(row: dict[str, Any]) -> None:
    container = cosmos_wars_container()
    if container is not None:
        container.upsert_item(dict(row))


def _save_rating_audit(row: dict[str, Any]) -> None:
    if not any(item.get("id") == row.get("id") for item in RATING_AUDIT_RECORDS):
        RATING_AUDIT_RECORDS.append(row)
    _save_war_document(row)


def _rating_audit_for_fight(fight_id: str, mode: str) -> dict[str, Any] | None:
    cached = next((row for row in RATING_AUDIT_RECORDS if row.get("fightId") == fight_id and row.get("mode") == mode), None)
    if cached is not None:
        return cached
    container = cosmos_wars_container()
    if container is None:
        return None
    query = "SELECT * FROM c WHERE c.docType = 'ratingAudit' AND c.fightId = @fight AND c.mode = @mode"
    rows = list(container.query_items(
        query=query,
        parameters=[{"name": "@fight", "value": fight_id}, {"name": "@mode", "value": mode}],
        enable_cross_partition_query=True,
    ))
    if not rows:
        return None
    RATING_AUDIT_RECORDS.append(rows[0])
    return rows[0]


def _rating_audits_for_mode(mode: str) -> list[dict[str, Any]]:
    mode = mode if mode in FIGHT_MODES else "cwa"
    container = cosmos_wars_container()
    if container is None:
        rows = [row for row in RATING_AUDIT_RECORDS if row.get("mode") == mode]
    else:
        rows = list(container.query_items(
            query="SELECT * FROM c WHERE c.docType = 'ratingAudit' AND c.mode = @mode ORDER BY c.appliedAt DESC",
            parameters=[{"name": "@mode", "value": mode}],
            enable_cross_partition_query=True,
        ))
    return sorted(rows, key=lambda row: str(row.get("appliedAt") or ""), reverse=True)


def _clean_audit_payload(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _rating_record(row: dict[str, Any], mode: str) -> dict[str, int]:
    record = row.get(f"{mode}Record")
    if not isinstance(record, dict):
        record = {}
    return {
        "wins": int(record.get("wins") or 0),
        "losses": int(record.get("losses") or 0),
        "draws": int(record.get("draws") or 0),
        "disputed": int(record.get("disputed") or 0),
    }


def _rating_eligibility(fight: dict[str, Any], result: dict[str, Any], mode: str) -> tuple[bool, str]:
    participants = {str(fight.get("creatorClanId") or ""), str(fight.get("opponentClanId") or "")}
    accepted = {str(value) for value in fight.get("acceptedBy", [])}
    if fight.get("status") != "completed":
        return False, "fight_not_completed"
    if not participants.issubset(accepted):
        return False, "mutual_acceptance_required"
    outcome = str(result.get("outcome") or "").strip().lower()
    if bool(result.get("disputed")) or outcome in {"disputed", "no contest", "no_contest"}:
        return False, "disputed_result"
    confidence = str(result.get("telemetryConfidence") or "").strip().lower()
    if confidence not in RATING_ACCEPTED_CONFIDENCE:
        return False, "telemetry_confidence_threshold_not_met"
    roster_value = fight.get("acceptedRosterSnapshots")
    if not isinstance(roster_value, dict):
        return False, "accepted_roster_snapshots_required"
    for clan_id in participants:
        snapshot = roster_value.get(clan_id)
        if not isinstance(snapshot, dict):
            return False, "accepted_roster_snapshots_required"
        member_count = int(snapshot.get("memberCount") or 0)
        if member_count < RATING_MIN_ROSTER_MEMBERS:
            return False, "roster_snapshot_threshold_not_met"
    if outcome == "draw":
        return True, "rateable"
    winner = normalize_clan_id(str(result.get("winnerClanId") or ""))
    if outcome != "win" or winner not in participants:
        return False, "valid_winner_required"
    if mode not in FIGHT_MODES:
        return False, "invalid_mode"
    return True, "rateable"


def _apply_rating_update(fight: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    terms = fight.get("terms") if isinstance(fight.get("terms"), dict) else {}
    mode = str(terms.get("mode") or "cwa").strip().lower()
    if mode not in FIGHT_MODES:
        mode = "cwa"
    fight_id = str(fight.get("id") or "")
    existing = _rating_audit_for_fight(fight_id, mode)
    if existing is not None:
        return {"applied": False, "reason": "already_applied", "auditId": existing.get("id"), "schemaVersion": existing.get("schemaVersion")}
    ok, reason = _rating_eligibility(fight, result, mode)
    if not ok:
        return {"applied": False, "reason": reason, "schemaVersion": RATING_SCHEMA_VERSION, "mode": mode}

    creator_id = str(fight.get("creatorClanId") or "")
    opponent_id = str(fight.get("opponentClanId") or "")
    creator = load_plugin_clan(creator_id) or {"clan_id": creator_id, "clan_name": creator_id, "members": []}
    opponent = load_plugin_clan(opponent_id) or {"clan_id": opponent_id, "clan_name": opponent_id, "members": []}
    winner_id = normalize_clan_id(str(result.get("winnerClanId") or ""))
    outcome = str(result.get("outcome") or "").strip().lower()
    def stored_rating(row: dict[str, Any]) -> int:
        value = row.get(f"{mode}Rating")
        return int(value) if value is not None else RATING_START

    before_was_rated = {creator_id: creator.get(f"{mode}Rating") is not None, opponent_id: opponent.get(f"{mode}Rating") is not None}
    before = {
        creator_id: stored_rating(creator),
        opponent_id: stored_rating(opponent),
    }
    expected_creator = 1 / (1 + 10 ** ((before[opponent_id] - before[creator_id]) / 400))
    score_creator = 0.5 if outcome == "draw" else (1.0 if winner_id == creator_id else 0.0)
    delta_creator = round(RATING_K_FACTOR * (score_creator - expected_creator))
    deltas = {creator_id: delta_creator, opponent_id: -delta_creator}
    after = {clan_id: before[clan_id] + deltas[clan_id] for clan_id in before}

    for clan_id, row, score in ((creator_id, creator, score_creator), (opponent_id, opponent, 1.0 - score_creator)):
        record = _rating_record(row, mode)
        if outcome == "draw":
            record["draws"] += 1
        elif score == 1.0:
            record["wins"] += 1
        else:
            record["losses"] += 1
        row[f"{mode}Rating"] = after[clan_id]
        row[f"{mode}Record"] = record
        row[f"{mode}RatingUpdatedAt"] = utc_now_iso()
        save_plugin_clan(row)

    audit = {
        "id": hashlib.sha256((RATING_SCHEMA_VERSION + "|" + fight_id + "|" + mode).encode("utf-8")).hexdigest(),
        "docType": "ratingAudit",
        "schemaVersion": RATING_SCHEMA_VERSION,
        "fightId": fight_id,
        "mode": mode,
        "appliedAt": utc_now_iso(),
        "input": _clean_audit_payload({
            "fightId": fight_id,
            "terms": terms,
            "termsHash": fight.get("termsHash"),
            "acceptedBy": fight.get("acceptedBy", []),
            "acceptedRosterSnapshots": fight.get("acceptedRosterSnapshots", {}),
            "result": result,
        }),
        "ratingsBefore": before,
        "ratingsBeforeWereRated": before_was_rated,
        "ratingsAfter": after,
        "ratingDeltas": deltas,
        "algorithm": {"name": "elo", "kFactor": RATING_K_FACTOR, "startRating": RATING_START},
    }
    _save_rating_audit(audit)
    return {"applied": True, "auditId": audit["id"], "schemaVersion": RATING_SCHEMA_VERSION, "mode": mode, "ratingDeltas": deltas}


def _reverse_rating_update(fight: dict[str, Any], reason: str) -> dict[str, Any]:
    mode = str((fight.get("terms") or {}).get("mode") or "cwa")
    audit = _rating_audit_for_fight(str(fight.get("id") or ""), mode)
    if audit is None or audit.get("reversedAt"):
        return {"reversed": False, "reason": "rating_not_applied" if audit is None else "already_reversed"}
    result = (audit.get("input") or {}).get("result") or {}
    winner = normalize_clan_id(str(result.get("winnerClanId") or ""))
    outcome = str(result.get("outcome") or "").lower()
    for clan_id, rating in (audit.get("ratingsBefore") or {}).items():
        clan = load_plugin_clan(clan_id) or {"clan_id": clan_id, "clan_name": clan_id, "members": []}
        clan[f"{mode}Rating"] = int(rating) if bool((audit.get("ratingsBeforeWereRated") or {}).get(clan_id)) else None
        record = _rating_record(clan, mode)
        key = "draws" if outcome == "draw" else ("wins" if clan_id == winner else "losses")
        record[key] = max(0, record[key] - 1)
        clan[f"{mode}Record"] = record
        save_plugin_clan(clan)
    audit["reversedAt"] = utc_now_iso()
    audit["reversalReason"] = str(reason)[:500]
    _save_war_document(audit)
    return {"reversed": True, "auditId": audit.get("id"), "mode": mode}


def _clean_evidence(value: Any) -> list[dict[str, Any]]:
    cleaned = []
    for row in (value if isinstance(value, list) else [])[:20]:
        if not isinstance(row, dict):
            continue
        evidence_type = str(row.get("type") or "other").strip().lower()
        if evidence_type not in {"outsider", "crasher", "telemetry", "screenshot", "other"}:
            evidence_type = "other"
        cleaned.append({"type": evidence_type, "eventIds": [str(item)[:128] for item in (row.get("eventIds") or [])[:50]], "note": str(row.get("note") or "").strip()[:500]})
    return cleaned


def _record_moderation(fight: dict[str, Any], action: str, session: dict[str, Any], detail: dict[str, Any]) -> None:
    row = {"id": str(uuid.uuid4()), "docType": "moderationAudit", "fightId": fight.get("id"), "action": action,
           "actorClanId": session.get("clanId"), "actorInstallHash": session.get("installHash"), "createdAt": utc_now_iso(),
           "detail": _clean_audit_payload(detail)}
    MODERATION_AUDIT_RECORDS.append(row)
    _save_war_document(row)


def _moderation_rows(fight_id: str) -> list[dict[str, Any]]:
    container = cosmos_wars_container()
    if container is None:
        return [row for row in MODERATION_AUDIT_RECORDS if row.get("fightId") == fight_id]
    return list(container.query_items(query="SELECT * FROM c WHERE c.docType = 'moderationAudit' AND c.fightId = @fight ORDER BY c.createdAt ASC", parameters=[{"name": "@fight", "value": fight_id}], enable_cross_partition_query=True))


def _load_challenge(challenge_id: str) -> dict[str, Any] | None:
    cached = next((row for row in CHALLENGES if row.get("id") == challenge_id), None)
    if cached is not None:
        return cached
    container = cosmos_wars_container()
    if container is None:
        return None
    query = "SELECT * FROM c WHERE c.id = @id AND c.docType = 'challenge'"
    rows = list(container.query_items(query=query, parameters=[{"name": "@id", "value": challenge_id}], enable_cross_partition_query=True))
    if not rows:
        return None
    CHALLENGES.append(rows[0])
    return rows[0]


def _confirmed_fights_for_clan(clan_id: str) -> list[dict[str, Any]]:
    container = cosmos_wars_container()
    if container is None:
        return [row for row in CHALLENGES if row.get("status") == "confirmed" and clan_id in {row.get("creatorClanId"), row.get("opponentClanId")}]
    query = "SELECT * FROM c WHERE c.docType = 'challenge' AND c.status = 'confirmed' AND (c.creatorClanId = @clan OR c.opponentClanId = @clan)"
    return list(container.query_items(query=query, parameters=[{"name": "@clan", "value": clan_id}], enable_cross_partition_query=True))


def _fight_for_event(clan_id: str, world: int, timestamp_ms: int) -> dict[str, Any] | None:
    try:
        observed = datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None
    for fight in _confirmed_fights_for_clan(clan_id):
        terms_value = fight.get("terms")
        terms: dict[str, Any] = terms_value if isinstance(terms_value, dict) else {}
        try:
            starts = datetime.fromisoformat(str(terms.get("startsAt") or "").replace("Z", "+00:00"))
            ends = starts + timedelta(minutes=int(terms.get("durationMinutes") or 0))
            fight_world = int(terms.get("world") or 0)
        except (TypeError, ValueError):
            continue
        if fight_world == world and starts <= observed <= ends:
            return fight
    return None


def _save_telemetry_event(row: dict[str, Any]) -> None:
    if not any(item.get("id") == row.get("id") for item in TELEMETRY_EVENTS):
        TELEMETRY_EVENTS.append(row)
    _save_war_document(row)


def _player_telemetry(player_hash: str, install_hash: str) -> list[dict[str, Any]]:
    container = cosmos_wars_container()
    if container is None:
        return [row for row in TELEMETRY_EVENTS if row.get("playerHash") == player_hash or (not row.get("playerHash") and row.get("installHash") == install_hash)]
    query = "SELECT * FROM c WHERE c.docType = 'telemetryEvent' AND (c.playerHash = @player OR (NOT IS_DEFINED(c.playerHash) AND c.installHash = @install))"
    parameters = [{"name": "@player", "value": player_hash}, {"name": "@install", "value": install_hash}]
    return list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))


def _fight_telemetry(fight_id: str) -> list[dict[str, Any]]:
    container = cosmos_wars_container()
    if container is None:
        return [row for row in TELEMETRY_EVENTS if row.get("fightId") == fight_id]
    return list(container.query_items(
        query="SELECT * FROM c WHERE c.docType = 'telemetryEvent' AND c.fightId = @fight",
        parameters=[{"name": "@fight", "value": fight_id}],
        enable_cross_partition_query=True,
    ))


def _empty_metrics() -> dict[str, int]:
    return {
        "fightsObserved": 0,
        "observedKills": 0,
        "deaths": 0,
        "returns": 0,
        "opponentDamage": 0,
        "friendlyFireDamage": 0,
        "damageInflicted": 0,
        "damageReceived": 0,
        "thirdPartyDamage": 0,
        "unverifiedExternalDamage": 0,
        "unattributedDamageReceived": 0,
        "activitySamples": 0,
        "eventsTracked": 0,
    }


def _accumulate_metric(metrics: dict[str, int], row: dict[str, Any]) -> None:
    event_type = str(row.get("type") or "")
    amount = max(0, int(row.get("amount") or 0))
    relation = str(row.get("relation") or "unknown")
    metrics["eventsTracked"] += 1
    if event_type == "kill_candidate":
        metrics["observedKills"] += max(1, amount)
    elif event_type == "death":
        metrics["deaths"] += max(1, amount)
    elif event_type == "return":
        metrics["returns"] += max(1, amount)
    elif event_type == "damage_dealt":
        metrics["opponentDamage"] += amount
        metrics["damageInflicted"] += amount
    elif event_type == "friendly_fire_damage":
        metrics["friendlyFireDamage"] += amount
        metrics["damageInflicted"] += amount
    elif event_type == "damage_taken":
        metrics["damageReceived"] += amount
        if relation == "non_own_clan":
            metrics["unverifiedExternalDamage"] += amount
        elif relation in {"unattributed", "unknown"}:
            metrics["unattributedDamageReceived"] += amount
    elif event_type == "third_party_damage":
        metrics["thirdPartyDamage"] += amount
    elif event_type in {"heartbeat", "location_sample"}:
        metrics["activitySamples"] += 1


def _public_event(row: dict[str, Any]) -> dict[str, Any]:
    player = row.get("publicPlayerName") or ("Private " + str(row.get("playerHash") or row.get("installHash") or "member")[:8])
    opponent = str(row.get("opponentName") or "").strip()
    public_opponent = "Private opponent " + hashlib.sha256(opponent.lower().encode("utf-8")).hexdigest()[:8] if opponent else None
    relation = row.get("relation") or "unknown"
    participant_classification = {"self": "reporting_player", "own_clan": "accepted_roster_or_own_clan"}.get(relation, "unattributed")
    if relation in {"own_clan", "non_own_clan"} and opponent:
        fight = _load_challenge(str(row.get("fightId") or ""))
        if fight is not None and fight.get("acceptedRosterSnapshots"):
            participant_classification = classify_participant(fight, str(row.get("clanId") or ""), opponent)
        elif relation == "non_own_clan":
            participant_classification = "outsider_or_unverified"
    elif relation == "non_own_clan":
        participant_classification = "outsider_or_unverified"
    return {
        "id": row.get("id"),
        "fightId": row.get("fightId"),
        "clanId": row.get("clanId"),
        "player": player,
        "playerPublic": bool(row.get("playerPublic")),
        "type": row.get("type"),
        "opponentName": public_opponent,
        "participantClassification": participant_classification,
        "amount": int(row.get("amount") or 0),
        "world": int(row.get("world") or 0),
        "tick": int(row.get("tick") or 0),
        "timestamp": int(row.get("timestamp") or 0),
        "observedAt": row.get("observedAt"),
        "evidence": row.get("evidence") or "legacy_client_observation",
        "confidence": row.get("confidence") or "unknown",
        "relation": relation,
        "location": row.get("location") or {"regionId": 0, "x": 0, "y": 0, "plane": 0},
    }


def _aggregate_fight_events(rows: list[dict[str, Any]]) -> dict[str, Any]:
    events = sorted((_public_event(row) for row in rows), key=lambda row: (row["timestamp"], row["tick"], str(row["id"])))
    totals = _empty_metrics()
    totals["fightsObserved"] = 1 if events else 0
    dimensions: dict[str, dict[str, int]] = {"eventTypes": {}, "confidence": {}, "evidence": {}, "relations": {}}
    clan_metrics: dict[str, dict[str, int]] = {}
    player_metrics: dict[str, dict[str, int]] = {}
    opponent_metrics: dict[str, dict[str, int]] = {}
    locations: dict[str, dict[str, Any]] = {}
    raw_by_id = {str(row.get("id")): row for row in rows}
    for event in events:
        raw = raw_by_id.get(str(event["id"]), event)
        _accumulate_metric(totals, raw)
        for dimension, value in (("eventTypes", event["type"]), ("confidence", event["confidence"]),
                                 ("evidence", event["evidence"]), ("relations", event["relation"])):
            key = str(value or "unknown")
            dimensions[dimension][key] = dimensions[dimension].get(key, 0) + 1
        for collection, key in ((clan_metrics, str(event["clanId"] or "unknown")),
                                (player_metrics, str(event["player"] or "unknown"))):
            metrics = collection.setdefault(key, _empty_metrics())
            metrics["fightsObserved"] = 1
            _accumulate_metric(metrics, raw)
        opponent = str(event.get("opponentName") or "").strip()
        if opponent:
            metrics = opponent_metrics.setdefault(opponent, _empty_metrics())
            metrics["fightsObserved"] = 1
            _accumulate_metric(metrics, raw)
        location = event.get("location") or {}
        region_id = int(location.get("regionId") or 0)
        if region_id:
            key = f"{region_id}:{int(location.get('x') or 0)}:{int(location.get('y') or 0)}:{int(location.get('plane') or 0)}"
            hotspot = locations.setdefault(key, {**location, "samples": 0})
            hotspot["samples"] += 1
    return {
        "totals": totals,
        "dimensions": dimensions,
        "byClan": clan_metrics,
        "byPlayer": player_metrics,
        "byOpponent": opponent_metrics,
        "locationHotspots": sorted(locations.values(), key=lambda row: (-row["samples"], row["regionId"])),
        "events": events,
    }



def _header(headers: dict[str, str] | None, name: str) -> str:
    for key, value in (headers or {}).items():
        if key.lower() == name.lower():
            return str(value).strip()
    return ""


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_session(install_hash: str, player_hash: str, clan_id: str, rank: int,
                   public_stats: bool = False, now: int | None = None, verified_leader: bool = False,
                   verified_moderator: bool = False) -> dict[str, Any]:
    issued_at = int(time.time() if now is None else now)
    token = secrets.token_urlsafe(32)
    capabilities = ["member:read", "telemetry:write"]
    if verified_leader:
        capabilities.extend(["leader:write", "challenge:write"])
    if verified_moderator:
        capabilities.append("moderation:write")
    session = {
        "id": _token_hash(token),
        "docType": "installationSession",
        "installHash": install_hash,
        "playerHash": player_hash,
        "clanId": clan_id,
        "observedClanRank": rank,
        "publicStats": bool(public_stats),
        "capabilities": capabilities,
        "issuedAtEpoch": issued_at,
        "expiresAtEpoch": issued_at + SESSION_SECONDS,
        "nonces": [],
        "requestTimes": [],
        "trustLevel": "server_verified_moderator" if verified_moderator else ("server_verified_leader_claim" if verified_leader else "registered_member"),
    }
    _save_session(session)
    return {
        "sessionToken": token,
        "expiresAt": datetime.fromtimestamp(session["expiresAtEpoch"], timezone.utc).isoformat(),
        "capabilities": capabilities,
        "trustLevel": session["trustLevel"],
    }


def authorize_write(headers: dict[str, str] | None, capability: str, now: int | None = None) -> dict[str, Any]:
    current = int(time.time() if now is None else now)
    authorization = _header(headers, "Authorization")
    if not authorization.startswith("Bearer "):
        return {"ok": False, "error": "missing_session"}
    session = _load_session(_token_hash(authorization[7:].strip()))
    if session is None or session.get("revokedAtEpoch"):
        return {"ok": False, "error": "invalid_session"}
    if int(session.get("expiresAtEpoch") or 0) <= current:
        return {"ok": False, "error": "expired_session"}
    if capability not in session.get("capabilities", []):
        return {"ok": False, "error": "capability_denied"}
    try:
        request_time = int(_header(headers, "X-CWB-Timestamp"))
        nonce = str(uuid.UUID(_header(headers, "X-CWB-Nonce")))
    except (TypeError, ValueError, AttributeError):
        return {"ok": False, "error": "invalid_request_proof"}
    if abs(current - request_time) > WRITE_CLOCK_SKEW_SECONDS:
        return {"ok": False, "error": "stale_request"}
    nonces = session.setdefault("nonces", [])
    if nonce in nonces:
        return {"ok": False, "error": "replayed_request"}
    recent = [value for value in session.setdefault("requestTimes", []) if current - int(value) < 60]
    if len(recent) >= WRITE_RATE_LIMIT:
        return {"ok": False, "error": "rate_limited", "retryAfter": 60}
    nonces.append(nonce)
    session["nonces"] = nonces[-100:]
    recent.append(current)
    session["requestTimes"] = recent
    try:
        _save_session(session)
    except Exception as exc:
        if getattr(exc, "status_code", None) in {409, 412}:
            INSTALL_SESSIONS.pop(str(session.get("id") or ""), None)
            return {"ok": False, "error": "concurrent_request"}
        raise
    return {"ok": True, "session": session}


def rotate_installation_session(headers: dict[str, str] | None) -> dict[str, Any]:
    authorized = authorize_write(headers, "member:read")
    if not authorized.get("ok"):
        return authorized
    session = authorized["session"]
    session["revokedAtEpoch"] = int(time.time())
    _save_session(session)
    clan = load_plugin_clan(str(session["clanId"])) or {}
    issued = _issue_session(session["installHash"], str(session.get("playerHash") or session["installHash"]), session["clanId"],
                            int(session.get("observedClanRank") or -1), bool(session.get("publicStats", False)),
                            verified_leader=_is_verified_leader(clan, str(session["installHash"])),
                            verified_moderator=_is_verified_moderator(clan, str(session["installHash"])))
    return {"ok": True, **issued}


def create_availability(payload: dict[str, Any] | None, headers: dict[str, str] | None) -> dict[str, Any]:
    authorized = authorize_write(headers, "leader:write")
    if not authorized.get("ok"):
        return authorized
    payload = payload if isinstance(payload, dict) else {}
    try:
        starts_at = datetime.fromisoformat(str(payload.get("startsAt") or "").replace("Z", "+00:00"))
        duration = int(payload.get("durationMinutes"))
        combat_min = int(payload.get("combatMin", 3))
        combat_max = int(payload.get("combatMax", 126))
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_availability"}
    if starts_at.tzinfo is None or not 5 <= duration <= 180 or combat_min < 3 or combat_max > 126 or combat_min > combat_max:
        return {"ok": False, "error": "invalid_availability"}
    mode = str(payload.get("mode") or "cwa").strip().lower()
    if mode not in FIGHT_MODES:
        return {"ok": False, "error": "invalid_availability"}
    session = authorized["session"]
    row = {
        "id": str(uuid.uuid4()),
        "docType": "availability",
        "clanPairKey": session["clanId"],
        "creatorClanId": session["clanId"],
        "startsAt": starts_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "durationMinutes": duration,
        "combatMin": combat_min,
        "combatMax": combat_max,
        "mode": mode,
        "notes": str(payload.get("notes") or "").strip()[:240],
        "createdAt": utc_now_iso(),
        "status": "open",
    }
    AVAILABILITY.append(row)
    _save_war_document(row)
    return {"ok": True, "availability": row}


def create_challenge(payload: dict[str, Any] | None, headers: dict[str, str] | None) -> dict[str, Any]:
    authorized = authorize_write(headers, "challenge:write")
    if not authorized.get("ok"):
        return authorized
    payload = payload if isinstance(payload, dict) else {}
    session = authorized["session"]
    opponent = normalize_clan_id(str(payload.get("opponentClanId") or ""))
    if not opponent or opponent == session["clanId"]:
        return {"ok": False, "error": "invalid_opponent"}
    try:
        normalized_terms = normalize_fight_terms(payload.get("terms") or {})
    except ValueError as exc:
        return {"ok": False, "error": "invalid_terms", "message": str(exc)}
    row = {
        "id": str(uuid.uuid4()),
        "docType": "challenge",
        "clanPairKey": "|".join(sorted([session["clanId"], opponent])),
        "creatorClanId": session["clanId"],
        "opponentClanId": opponent,
        "terms": normalized_terms,
        "termsHash": terms_hash(normalized_terms),
        "acceptedBy": [session["clanId"]],
        "status": "proposed",
        "createdAt": utc_now_iso(),
        "updatedAt": utc_now_iso(),
    }
    CHALLENGES.append(row)
    _save_war_document(row)
    return {"ok": True, "challenge": row}


def get_challenges(headers: dict[str, str] | None) -> dict[str, Any]:
    authorized = authorize_write(headers, "member:read")
    if not authorized.get("ok"):
        return authorized
    clan_id = str(authorized["session"]["clanId"])
    container = cosmos_wars_container()
    if container is None:
        rows = [row for row in CHALLENGES if clan_id in {row.get("creatorClanId"), row.get("opponentClanId")}]
    else:
        query = "SELECT * FROM c WHERE c.docType = 'challenge' AND (c.creatorClanId = @clan OR c.opponentClanId = @clan) ORDER BY c.updatedAt DESC"
        rows = list(container.query_items(query=query, parameters=[{"name": "@clan", "value": clan_id}], enable_cross_partition_query=True))
    visible = [{key: value for key, value in row.items() if key not in {"_etag", "_rid", "_self", "_attachments", "_ts", "docType", "clanPairKey"}} for row in rows]
    return {"ok": True, "challenges": visible}


def get_moderation_audit(challenge_id: str, headers: dict[str, str] | None) -> dict[str, Any]:
    authorized = authorize_write(headers, "member:read")
    if not authorized.get("ok"):
        return authorized
    challenge = _load_challenge(challenge_id)
    if challenge is None:
        return {"ok": False, "error": "challenge_not_found"}
    session = authorized["session"]
    moderator = "moderation:write" in session.get("capabilities", [])
    if not moderator and session.get("clanId") not in {challenge.get("creatorClanId"), challenge.get("opponentClanId")}:
        return {"ok": False, "error": "challenge_forbidden"}
    records = []
    for row in _moderation_rows(challenge_id):
        visible = {key: value for key, value in row.items() if key not in {"actorInstallHash", "_etag", "_rid", "_self", "_attachments", "_ts", "docType"}}
        records.append(visible)
    return {"ok": True, "fightId": challenge_id, "status": challenge.get("status"),
            "access": "moderator" if moderator else "member_read_only",
            "allowedActions": ["correct", "void"] if moderator else [], "records": records}


def moderate_challenge(challenge_id: str, payload: dict[str, Any] | None, headers: dict[str, str] | None) -> dict[str, Any]:
    authorized = authorize_write(headers, "moderation:write")
    if not authorized.get("ok"):
        return authorized
    challenge = _load_challenge(challenge_id)
    if challenge is None:
        return {"ok": False, "error": "challenge_not_found"}
    request_payload: dict[str, Any] = payload if isinstance(payload, dict) else {}
    action = str(request_payload.get("action") or "").strip().lower()
    reason = str(request_payload.get("reason") or "").strip()[:1000]
    if action not in {"correct", "void"} or not reason:
        return {"ok": False, "error": "invalid_moderation_action"}
    if challenge.get("status") not in {"disputed", "completed"}:
        return {"ok": False, "error": "moderation_state_conflict"}
    result: dict[str, Any] = dict(request_payload["result"]) if isinstance(request_payload.get("result"), dict) else {}
    outcome = str(result.get("outcome") or "").strip().lower()
    if action == "correct" and outcome not in {"win", "draw", "no_contest"}:
        return {"ok": False, "error": "invalid_corrected_result"}
    reversal = _reverse_rating_update(challenge, "moderator " + action + ": " + reason)
    if action == "void":
        challenge["status"] = "voided"
        challenge["voidReason"] = reason
        rating_update = {"applied": False, "reason": "voided_result"}
    else:
        result["disputed"] = False
        challenge["result"] = _clean_audit_payload(result)
        challenge["status"] = "completed"
        challenge["correctedAt"] = utc_now_iso()
        rating_update = _apply_rating_update(challenge, challenge["result"])
        challenge["ratingUpdate"] = rating_update
    challenge["updatedAt"] = utc_now_iso()
    _record_moderation(challenge, "result_" + action, authorized["session"], {"reason": reason, "result": challenge.get("result") if action == "correct" else None, "ratingReversal": reversal})
    _save_war_document(challenge)
    return {"ok": True, "challenge": challenge, "ratingReversal": reversal, "ratingUpdate": rating_update}


def update_challenge(challenge_id: str, payload: dict[str, Any] | None, headers: dict[str, str] | None) -> dict[str, Any]:
    authorized = authorize_write(headers, "challenge:write")
    if not authorized.get("ok"):
        return authorized
    challenge = _load_challenge(challenge_id)
    if challenge is None:
        return {"ok": False, "error": "challenge_not_found"}
    actor = str(authorized["session"]["clanId"])
    participants = {challenge.get("creatorClanId"), challenge.get("opponentClanId")}
    if actor not in participants:
        return {"ok": False, "error": "challenge_forbidden"}
    payload = payload if isinstance(payload, dict) else {}
    action = str(payload.get("action") or "").strip().lower()
    allowed_by_state = {
        "proposed": {"accept", "counter", "reject", "cancel"},
        "reconfirm_required": {"accept", "counter", "reject", "cancel"},
        "confirmed": {"complete", "counter", "cancel"},
        "result_confirmation_required": {"complete"},
        "completed": {"dispute"},
    }
    if action not in allowed_by_state.get(str(challenge.get("status") or ""), set()):
        return {"ok": False, "error": "challenge_state_conflict"}
    if action == "cancel" and actor != challenge.get("creatorClanId"):
        return {"ok": False, "error": "challenge_forbidden"}
    if action == "reject" and actor != challenge.get("opponentClanId"):
        return {"ok": False, "error": "challenge_forbidden"}
    if action == "complete":
        if challenge.get("status") not in {"confirmed", "result_confirmation_required"}:
            return {"ok": False, "error": "challenge_not_confirmed"}
        updated = json.loads(json.dumps(challenge))
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        result_hash = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        proposal = updated.get("resultProposal") if isinstance(updated.get("resultProposal"), dict) else None
        if proposal is None:
            updated["resultProposal"] = {"hash": result_hash, "result": _clean_audit_payload(result), "submittedBy": [actor], "submittedAt": utc_now_iso()}
            updated["status"] = "result_confirmation_required"
            updated["updatedAt"] = utc_now_iso()
            challenge.clear()
            challenge.update(updated)
            _save_war_document(challenge)
            return {"ok": True, "challenge": challenge, "ratingUpdate": {"applied": False, "reason": "mutual_result_confirmation_required"}}
        if actor in set(proposal.get("submittedBy") or []):
            return {"ok": False, "error": "result_confirmation_requires_other_clan"}
        if not secrets.compare_digest(str(proposal.get("hash") or ""), result_hash):
            return {"ok": False, "error": "result_confirmation_mismatch"}
        result = dict(proposal.get("result") or {})
        updated["status"] = "completed"
        updated["completedAt"] = utc_now_iso()
        updated["result"] = _clean_audit_payload(result)
        updated.pop("resultProposal", None)
        updated["updatedAt"] = utc_now_iso()
        challenge.clear()
        challenge.update(updated)
        rating_update = _apply_rating_update(challenge, updated["result"])
        challenge["ratingUpdate"] = rating_update
        _save_war_document(challenge)
        return {"ok": True, "challenge": challenge, "ratingUpdate": rating_update}
    if action == "dispute":
        if challenge.get("status") != "completed":
            return {"ok": False, "error": "result_not_completed"}
        reason_code = str(payload.get("reasonCode") or "").strip().lower()
        if reason_code not in {"wrong_result", "third_party_interference", "telemetry_gap", "roster_violation", "rules_violation", "other"}:
            return {"ok": False, "error": "invalid_dispute_reason"}
        detail = {"reasonCode": reason_code, "statement": str(payload.get("statement") or "").strip()[:1000], "evidence": _clean_evidence(payload.get("evidence"))}
        reversal = _reverse_rating_update(challenge, "participant dispute: " + reason_code)
        challenge["status"] = "disputed"
        challenge["dispute"] = detail
        challenge["updatedAt"] = utc_now_iso()
        _record_moderation(challenge, "dispute_opened", authorized["session"], detail)
        _save_war_document(challenge)
        return {"ok": True, "challenge": challenge, "ratingReversal": reversal}
    try:
        updated = apply_challenge_action(challenge, action, actor, payload.get("terms"))
    except ValueError as exc:
        return {"ok": False, "error": "invalid_challenge_action", "message": str(exc)}
    challenge.clear()
    challenge.update(updated)
    if challenge.get("status") == "confirmed":
        snapshots = dict(challenge.get("acceptedRosterSnapshots") or {})
        for clan_id in (str(challenge.get("creatorClanId") or ""), str(challenge.get("opponentClanId") or "")):
            if clan_id and clan_id not in snapshots:
                clan = load_plugin_clan(clan_id) or {}
                snapshots[clan_id] = json.loads(json.dumps(clan.get("rosterSnapshot") or _roster_snapshot([], clan_id)))
        challenge["acceptedRosterSnapshots"] = snapshots
    _save_war_document(challenge)
    return {"ok": True, "challenge": challenge}


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
    install_hash = _install_hash(install_id)
    player_hash = _player_hash(clan_id, player_name) if player_name else hashlib.sha256((clan_id + "\0" + install_hash).encode("utf-8")).hexdigest()
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
    try:
        observed_rank = int(payload.get("clanRank") or -1)
    except (TypeError, ValueError):
        observed_rank = -1
    member_payload = {
        "installHash": install_hash,
        "playerHash": player_hash,
        "displayName": player_name if public_stats and player_name else "Private member",
        "public": public_stats,
        "clanRank": observed_rank,
        "pluginVersion": str(payload.get("pluginVersion") or "unknown")[:32],
        "lastSeenAt": now,
    }
    if member is None:
        members.append(member_payload)
    else:
        member.clear()
        member.update(member_payload)
    row["member_count"] = len(members)
    roster_payload = payload.get("rosterMembers")
    row["rosterSnapshot"] = _roster_snapshot(roster_payload if isinstance(roster_payload, list) else [player_name], clan_id)
    row["updatedAt"] = now
    save_plugin_clan(row)
    _revoke_installation_sessions(install_hash)
    session = _issue_session(install_hash, player_hash, clan_id, observed_rank, public_stats,
                             verified_leader=_is_verified_leader(row, install_hash),
                             verified_moderator=_is_verified_moderator(row, install_hash))
    return {
        "ok": True,
        "clanId": clan_id,
        "registeredMembers": row["member_count"],
        "publicStats": public_stats,
        "serverTime": now,
        **session,
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
        "rankings": {
            "cwa": {
                "rank": row.get("cwaRank"),
                "rating": row.get("cwaRating"),
                "record": row.get("cwaRecord") or {"wins": 0, "losses": 0, "draws": 0, "disputed": 0},
                "status": "ranked" if row.get("cwaRating") is not None else "unrated",
            },
            "wildy": {
                "rank": row.get("wildyRank"),
                "rating": row.get("wildyRating"),
                "record": row.get("wildyRecord") or {"wins": 0, "losses": 0, "draws": 0, "disputed": 0},
                "status": "ranked" if row.get("wildyRating") is not None else "unrated",
            },
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
    container = cosmos_wars_container()
    if container is None:
        rows = list(AVAILABILITY)
    else:
        query = "SELECT * FROM c WHERE c.docType = 'availability' AND c.status = 'open' ORDER BY c.startsAt ASC"
        rows = list(container.query_items(query=query, enable_cross_partition_query=True))
    availability = [
        {
            "id": row.get("id"),
            "creatorClanId": row.get("creatorClanId"),
            "startsAt": row.get("startsAt"),
            "durationMinutes": row.get("durationMinutes"),
            "combatMin": row.get("combatMin"),
            "combatMax": row.get("combatMax"),
            "mode": row.get("mode") or "cwa",
            "notes": row.get("notes"),
            "status": row.get("status"),
        }
        for row in rows
    ]
    if container is None:
        challenge_rows = list(CHALLENGES)
    else:
        challenge_rows = list(container.query_items(
            query="SELECT * FROM c WHERE c.docType = 'challenge' AND (c.status = 'confirmed' OR c.status = 'completed')",
            enable_cross_partition_query=True,
        ))

    def public_fight(row: dict[str, Any]) -> dict[str, Any]:
        terms_value = row.get("terms")
        terms: dict[str, Any] = terms_value if isinstance(terms_value, dict) else {}
        return {
            "id": row.get("id"),
            "creatorClanId": row.get("creatorClanId"),
            "opponentClanId": row.get("opponentClanId"),
            "startsAt": terms.get("startsAt"),
            "durationMinutes": terms.get("durationMinutes"),
            "combatMin": terms.get("combatMin"),
            "combatMax": terms.get("combatMax"),
            "mode": terms.get("mode") or "cwa",
            "status": row.get("status"),
        }

    scheduled = [public_fight(row) for row in challenge_rows if row.get("status") == "confirmed"]
    history = [public_fight(row) for row in challenge_rows if row.get("status") == "completed"]
    return {
        "generatedAt": utc_now_iso(),
        "source": "Clan War Board plugin submissions",
        "privacy": "public availability only; exact accepted world/rally notes hidden until agreement",
        "availability": availability,
        "scheduled": scheduled,
        "history": history,
        "emptyState": "No real scheduled fights have been posted yet. Authorized clan leaders can publish availability from the RuneLite panel.",
        "fightSetupFields": FIGHT_SETUP_FIELDS,
    }


def _fight_is_completed(fight: dict[str, Any]) -> bool:
    if fight.get("status") == "completed":
        return True
    if fight.get("status") != "confirmed":
        return False
    terms = fight.get("terms")
    if not isinstance(terms, dict):
        return False
    try:
        starts_at = datetime.fromisoformat(str(terms.get("startsAt") or "").replace("Z", "+00:00"))
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    try:
        duration = int(terms.get("durationMinutes") or 0)
    except (TypeError, ValueError):
        return False
    return duration > 0 and datetime.now(timezone.utc) >= starts_at + timedelta(minutes=duration)


def get_past_battles() -> dict[str, Any]:
    container = cosmos_wars_container()
    if container is None:
        fights = [row for row in CHALLENGES if _fight_is_completed(row)]
    else:
        candidates = list(container.query_items(
            query="SELECT * FROM c WHERE c.docType = 'challenge' AND c.status IN ('confirmed', 'completed')",
            enable_cross_partition_query=True,
        ))
        fights = [row for row in candidates if _fight_is_completed(row)]
    battles = []
    for fight in fights:
        terms_value = fight.get("terms")
        terms: dict[str, Any] = terms_value if isinstance(terms_value, dict) else {}
        result_value = fight.get("result")
        result: dict[str, Any] = result_value if isinstance(result_value, dict) else {}
        battles.append({
            "fightId": fight.get("id"),
            "creatorClanId": fight.get("creatorClanId"),
            "opponentClanId": fight.get("opponentClanId"),
            "startsAt": terms.get("startsAt"),
            "outcome": result.get("outcome"),
            "winnerClanId": result.get("winnerClanId"),
            "confirmedByBothClans": True,
        })
    battles.sort(key=lambda row: str(row.get("startsAt") or ""), reverse=True)
    return {
        "generatedAt": utc_now_iso(),
        "source": "Clan War Board mutually confirmed results",
        "privacy": "completed clan results only; the production plugin does not upload opponent, combat, or location telemetry",
        "battles": battles,
        "emptyState": "No real completed Clan War Board fights have been published yet.",
    }


def get_public_fight_summary(fight_id: str) -> dict[str, Any] | None:
    fight = _load_challenge(fight_id)
    if fight is None or not _fight_is_completed(fight):
        return None
    terms_value = fight.get("terms")
    terms: dict[str, Any] = terms_value if isinstance(terms_value, dict) else {}
    result_value = fight.get("result")
    result: dict[str, Any] = result_value if isinstance(result_value, dict) else {}
    return {
        "generatedAt": utc_now_iso(),
        "source": "mutually confirmed clan result",
        "privacy": "clan-level result only; no opponent, combat, player, or location observations are published",
        "fight": {
            "id": fight.get("id"),
            "creatorClanId": fight.get("creatorClanId"),
            "opponentClanId": fight.get("opponentClanId"),
            "status": "completed",
            "terms": {
                "startsAt": terms.get("startsAt"),
                "durationMinutes": terms.get("durationMinutes"),
                "combatMin": terms.get("combatMin"),
                "combatMax": terms.get("combatMax"),
                "mode": terms.get("mode") or "cwa",
                "returnsAllowed": (terms.get("mode") or "cwa") == "wildy" and bool(terms.get("returnsAllowed", True)),
                "rules": terms.get("rules"),
            },
            "result": {
                "outcome": result.get("outcome"),
                "winnerClanId": result.get("winnerClanId"),
                "confirmedByBothClans": True,
            },
        },
    }


def get_fight_setup_schema() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "requiredFields": FIGHT_SETUP_FIELDS,
        "agreementModel": "Both leaders must accept the exact terms hash. Changes require reconfirmation.",
        "defaultMode": "cwa",
        "modes": FIGHT_MODES,
    }


def get_fight_modes() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "defaultMode": "cwa",
        "modes": FIGHT_MODES,
        "membershipValidation": "Each clan leader confirms participation and the final clan-level result; the production plugin does not upload rosters or observations about other players.",
        "resultPublication": "A clan-level result is published only after both participating clans confirm the same outcome.",
    }



def get_win_judging_system() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "system": "mutual_result_confirmation",
        "summary": "Clan War Board publishes a winner only when both participating clan leaders confirm the same result.",
        "requiredBeforeFight": [
            "both leaders accept the same terms hash",
            "scheduled start and end time are locked",
            "fight location and world are locked privately",
            "combat bracket and allowed return rules are locked",
        ],
        "winnerSignals": [
            {"name": "matching leader confirmations", "weight": 1, "description": "both participating clans submit the same outcome and winner"},
            {"name": "no active dispute", "weight": 1, "description": "a disputed result remains unpublished and does not affect ratings"},
        ],
        "outcomes": [
            "win",
            "loss",
            "draw",
            "disputed",
            "no contest",
        ],
        "confidenceRules": [
            "both participating leaders must confirm an identical result",
            "missing or conflicting confirmation prevents publication",
            "a dispute pauses publication and rating changes pending moderation",
        ],
        "publicLeaderboardPolicy": "Only mutually confirmed, non-disputed clan results affect leaderboard rating.",
        "modeSystems": {
            "cwa": {
                "returnsAllowed": False,
                "signals": ["mutuallyConfirmedResult"],
                "note": "CWA ratings use the mutually confirmed clan result only.",
            },
            "wildy": {
                "returnsAllowed": True,
                "signals": ["mutuallyConfirmedResult"],
                "note": "Wildy ratings use the mutually confirmed clan result only.",
            },
        },
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

def get_competitive_leaderboard(mode: str = "cwa") -> dict[str, Any]:
    mode = mode.lower().strip()
    if mode not in FIGHT_MODES:
        mode = "cwa"
    base = get_leaderboard()
    standings = []
    clans = sorted(
        base.get("standings", []),
        key=lambda clan: (((clan.get("rankings") or {}).get(mode, {}).get("rating") is None), -int(((clan.get("rankings") or {}).get(mode, {}).get("rating") or 0)), str(clan.get("clan_name") or "")),
    )
    for index, clan in enumerate(clans, start=1):
        standings.append({
            "rank": index,
            "clan_id": clan.get("clan_id"),
            "clan_name": clan.get("clan_name"),
            "clan_type": clan.get("clan_type"),
            "member_count": clan.get("member_count"),
            "rating": (clan.get("rankings") or {}).get(mode, {}).get("rating"),
            "record": (clan.get("rankings") or {}).get(mode, {}).get("record") or {"wins": 0, "losses": 0, "draws": 0, "disputed": 0},
            "ratingStatus": (clan.get("rankings") or {}).get(mode, {}).get("status") or "unrated",
        })
    return {
        "generatedAt": utc_now_iso(),
        "source": "Clan War Board plugin completed fight results",
        "mode": mode,
        "modeLabel": FIGHT_MODES[mode]["label"],
        "availableModes": list(FIGHT_MODES),
        "leaderboardPolicy": get_win_judging_system()["publicLeaderboardPolicy"],
        "standings": standings,
    }


def get_rating_audit_records(mode: str = "cwa") -> dict[str, Any]:
    mode = mode.lower().strip()
    if mode not in FIGHT_MODES:
        mode = "cwa"
    records = []
    for row in _rating_audits_for_mode(mode):
        raw_input = row.get("input")
        audit_input: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}
        raw_result = audit_input.get("result")
        result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {}
        records.append({
            "id": row.get("id"), "schemaVersion": row.get("schemaVersion"), "fightId": row.get("fightId"),
            "mode": row.get("mode"), "appliedAt": row.get("appliedAt"), "reversedAt": row.get("reversedAt"),
            "reversalReason": row.get("reversalReason"), "termsHash": audit_input.get("termsHash"),
            "result": {"outcome": result.get("outcome"), "winnerClanId": result.get("winnerClanId"), "telemetryConfidence": result.get("telemetryConfidence")},
            "ratingsBefore": row.get("ratingsBefore"), "ratingsAfter": row.get("ratingsAfter"),
            "ratingDeltas": row.get("ratingDeltas"), "algorithm": row.get("algorithm"),
        })
    return {
        "generatedAt": utc_now_iso(),
        "source": "versioned Clan War Board rating audit records",
        "mode": mode,
        "schemaVersion": RATING_SCHEMA_VERSION,
        "records": records,
    }

def submit_telemetry_batch(payload: dict[str, Any] | None, client_headers: dict[str, str] | None = None) -> dict[str, Any]:
    authorized = authorize_write(client_headers, "telemetry:write")
    if not authorized.get("ok"):
        return authorized
    session = authorized["session"]
    session_clan_id = str(session["clanId"])
    install_hash = str(session["installHash"])
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
        if event_type not in {"heartbeat", "damage_dealt", "friendly_fire_damage", "damage_taken", "death", "kill_candidate", "return", "location_sample", "third_party_damage", "attack_style", "off_prayer_hit", "bind_cast", "bind_landed", "pile_target", "prayer_switch", "gear_switch", "food_eaten"}:
            continue
        if normalize_clan_id(str(event.get("clanName") or "")) != session_clan_id:
            continue
        try:
            amount = max(0, int(event.get("amount") or 0))
            world = int(event.get("world") or 0)
            tick = max(0, int(event.get("tick") or 0))
            timestamp_ms = int(event.get("timestamp") or 0)
            region_id = max(0, int(event.get("regionId") or 0))
            x = max(0, int(event.get("x") or 0))
            y = max(0, int(event.get("y") or 0))
            plane = int(event.get("plane") or 0)
        except (TypeError, ValueError):
            continue
        evidence = str(event.get("evidence") or "unspecified")[:64]
        confidence = str(event.get("confidence") or "unknown")[:32]
        relation = str(event.get("relation") or "unknown")[:32]
        if confidence not in {"high", "medium", "low", "unknown", "high_amount_low_source"}:
            confidence = "unknown"
        if relation not in {"self", "own_clan", "non_own_clan", "unattributed", "none", "unknown"}:
            relation = "unknown"
        if plane < 0 or plane > 3 or x > 20000 or y > 20000 or region_id > 65535:
            continue
        fight = _fight_for_event(session_clan_id, world, timestamp_ms)
        if fight is None:
            continue
        identity = "|".join([
            install_hash, str(fight.get("id") or ""), event_type, str(timestamp_ms), str(tick),
            str(world), str(amount), str(event.get("opponentName") or ""), evidence, relation,
        ])
        row = {
            "id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
            "docType": "telemetryEvent",
            "clanPairKey": fight["clanPairKey"],
            "fightId": fight["id"],
            "clanId": session_clan_id,
            "installHash": install_hash,
            "playerHash": str(session.get("playerHash") or install_hash),
            "type": event_type,
            "playerPublic": bool(session.get("publicStats", False)),
            "publicPlayerName": event.get("playerName") if bool(session.get("publicStats", False)) else None,
            "opponentName": str(event.get("opponentName") or "")[:12] or None,
            "amount": amount,
            "world": world,
            "tick": tick,
            "timestamp": timestamp_ms,
            "observedAt": datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).isoformat(),
            "evidence": evidence,
            "confidence": confidence,
            "relation": relation,
            "location": {"regionId": region_id, "x": x, "y": y, "plane": plane},
            "schemaVersion": 2,
        }
        _save_telemetry_event(row)
        accepted_events.append(row)
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
            "notes": "Only events matched to a confirmed fight world and scheduled window are stored.",
        },
        "stored": "cosmos" if storage_backend() == "cosmos" else "memory-local-only",
    }


def get_my_player_metrics(headers: dict[str, str] | None) -> dict[str, Any]:
    authorized = authorize_write(headers, "member:read")
    if not authorized.get("ok"):
        return authorized
    session = authorized["session"]
    events = _player_telemetry(str(session.get("playerHash") or session["installHash"]), str(session["installHash"]))
    metrics = _empty_metrics()
    metrics["fightsObserved"] = len({str(row.get("fightId")) for row in events if row.get("fightId")})
    for row in events:
        _accumulate_metric(metrics, row)
    return {
        "ok": True,
        "clanId": session["clanId"],
        "privacy": "authenticated installation owner only",
        "source": "persisted confirmed-fight telemetry",
        "generatedAt": utc_now_iso(),
        "metrics": metrics,
        "events": sorted((_public_event(row) for row in events), key=lambda row: (row["timestamp"], row["tick"]), reverse=True)[:500],
    }


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "clan-war-board-service",
        "generatedAt": utc_now_iso(),
        "storage": "cosmos" if storage_backend() == "cosmos" else "memory-local-only",
        "productionReadyStorage": storage_backend() == "cosmos",
    }
