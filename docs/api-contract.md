# API Contract Draft

This contract is the target shape for the Clan War Board service. It keeps public website reads separate from plugin authenticated writes.

## Versioning

All API responses include:

```json
{
  "apiVersion": "2026-07-14",
  "requestId": "..."
}
```

Breaking changes use a new route prefix later, e.g. `/api/v2/...`.

## Core data models

### Clan

```json
{
  "id": "clan_trapistan",
  "name": "TRAPISTAN",
  "normalizedName": "trapistan",
  "verificationStatus": "unverified|claimed|verified",
  "womGroupId": 12345,
  "pluginInstallCount": 58,
  "recentActiveMembers": 42,
  "createdAt": "2026-07-14T00:00:00Z"
}
```

### Plugin install/member heartbeat

```json
{
  "installId": "uuid",
  "playerName": "Oyama",
  "clanId": "clan_trapistan",
  "clanName": "TRAPISTAN",
  "observedRank": "Administrator",
  "leaderEligible": true,
  "pluginVersion": "1.0.0",
  "runeliteVersion": "...",
  "lastSeenAt": "2026-07-14T00:00:00Z"
}
```

### Availability post

```json
{
  "id": "avail_...",
  "creatorClanId": "clan_trapistan",
  "creatorPlayer": "Oyama",
  "status": "open|matched|expired|cancelled",
  "startsAt": "2026-07-19T20:00:00Z",
  "timeWindowMinutes": 30,
  "targetSizeMin": 40,
  "targetSizeMax": 60,
  "warType": "wilderness_multi",
  "publicRulesSummary": "Returns allowed; multi fight",
  "privateTerms": {
    "world": 330,
    "hotspot": "Lava Dragons",
    "rallyNotes": "Private until confirmed"
  },
  "visibility": "public_availability_private_terms",
  "termsHash": "sha256..."
}
```

### Fight application

```json
{
  "id": "app_...",
  "availabilityPostId": "avail_...",
  "challengerClanId": "clan_rival",
  "challengerLeader": "OtherLeader",
  "message": "We can do Sunday 8 ET",
  "status": "pending|accepted|countered|rejected|withdrawn",
  "createdAt": "2026-07-14T00:00:00Z"
}
```

### Confirmed fight

```json
{
  "id": "fight_...",
  "status": "confirmed|live|aggregation_pending|published|cancelled|disputed",
  "clans": ["clan_trapistan", "clan_rival"],
  "startsAt": "2026-07-19T20:00:00Z",
  "endsAt": "2026-07-19T21:00:00Z",
  "termsHash": "sha256...",
  "termsAcceptedBy": [
    { "clanId": "clan_trapistan", "playerName": "Oyama", "acceptedAt": "..." },
    { "clanId": "clan_rival", "playerName": "OtherLeader", "acceptedAt": "..." }
  ]
}
```

### Fight event observation

Submitted in batches:

```json
{
  "fightId": "fight_...",
  "events": [
    {
      "clientEventId": "uuid",
      "observedAt": "2026-07-19T20:12:34Z",
      "type": "damage_dealt|damage_taken|kill_observed|death_observed|return_detected|participant_seen|third_party_interaction",
      "actor": { "playerName": "MemberA", "clanId": "clan_trapistan" },
      "target": { "playerName": "EnemyB", "clanId": "clan_rival" },
      "world": 330,
      "regionId": 12345,
      "value": 32,
      "metadata": {
        "weaponCategory": "unknown",
        "confidence": "client_observed"
      }
    }
  ]
}
```

The server returns accepted/rejected counts, not immediate public results.

### Published fight summary

```json
{
  "fightId": "fight_...",
  "status": "published",
  "winnerClanId": "clan_trapistan",
  "winnerConfidence": "medium",
  "scoreExplanation": "TRAPISTAN had higher kills, returns, and sustained presence; third-party interference was moderate.",
  "overview": {
    "durationMinutes": 60,
    "clanCount": 2,
    "peakParticipants": 103,
    "thirdPartyInteractions": 27,
    "observedKills": 61,
    "observedDeaths": 58,
    "observedReturns": 142
  },
  "byClan": [
    {
      "clanId": "clan_trapistan",
      "kills": 34,
      "deaths": 27,
      "returns": 79,
      "damageDealt": 18233,
      "damageTaken": 15900,
      "activeMembers": 51,
      "presenceMinutes": 2400
    }
  ],
  "caveats": ["third_party_interference_moderate"]
}
```

## Endpoints

### Register plugin install

```text
POST /api/plugin/register
```

Request:

```json
{
  "installId": "uuid",
  "playerName": "Oyama",
  "clanName": "TRAPISTAN",
  "observedRank": "Administrator",
  "pluginVersion": "1.0.0",
  "runeliteVersion": "..."
}
```

Response:

```json
{
  "installToken": "opaque-short-lived-or-rotatable-token",
  "member": { "leaderEligible": true, "clanId": "clan_trapistan" }
}
```

### Heartbeat

```text
POST /api/plugin/heartbeat
```

Purpose:

- maintain active plugin member count,
- refresh leader eligibility,
- detect install/member churn,
- support clan readiness counts.

### Browse fights

```text
GET /api/plugin/fights/browse?warType=wilderness_multi&startsAfter=...
```

Returns public availability plus member-visible fields where authorized.

### Create availability

```text
POST /api/plugin/availability
```

Requires leader eligibility.

### Apply as interested

```text
POST /api/plugin/availability/{postId}/apply
```

Requires challenger leader eligibility.

### Accept application

```text
POST /api/plugin/applications/{applicationId}/accept
```

Requires original post leader eligibility and matching terms hash.

### Submit event batch

```text
POST /api/plugin/fights/{fightId}/events
```

Requires registered install, fight live window, membership or third-party observation context.

### Public website endpoints

```text
GET /api/public/leaderboard
GET /api/public/clans/{clanId}
GET /api/public/fights/{fightId}/summary
GET /api/public/availability
```

These are read-only and privacy-filtered.

## Rejection examples

### Member opens leader panel

Plugin local UI should show this before calling leader write endpoints:

```text
Leader access required. Your current clan rank does not allow fight management.
```

If still called, service returns:

```json
{
  "error": "leader_access_required",
  "message": "Your current clan rank does not allow fight management."
}
```

### Terms changed after acceptance

```json
{
  "error": "terms_reconfirmation_required",
  "message": "Fight terms changed after acceptance. Both leaders must confirm the updated terms."
}
```
