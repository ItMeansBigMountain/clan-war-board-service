# API Security and Traffic Model

## Important reality check

We can make the API RuneLite-plugin-oriented, but we cannot make a public Java client impossible to imitate. Any secret embedded in a RuneLite plugin can be extracted. Therefore, the system must not rely on a single static plugin secret.

The secure design is layered:

1. Publish no public write capability from the website.
2. Require plugin device registration for write APIs.
3. Require leader authorization for leader actions.
4. Require multiple independent observations for fight metrics.
5. Rate-limit by install, player, clan, IP/network, endpoint, and behavior.
6. Treat telemetry as evidence, not truth.
7. Publish completed analytics only after aggregation/sanity checks.

## API surfaces

### Public read API

Used by the website and plugin:

```text
GET /api/public/leaderboard
GET /api/public/clans/{clanId}
GET /api/public/fights/{fightId}/summary
GET /api/public/availability
```

Rules:

- cache heavily,
- no secrets,
- no live intel,
- no exact upcoming world/location unless explicitly public,
- safe for website use.

### Plugin read API

Used by registered plugin clients:

```text
GET /api/plugin/me
GET /api/plugin/my-clan
GET /api/plugin/fights/browse
GET /api/plugin/fights/{fightId}
GET /api/plugin/fights/{fightId}/live-overview
```

Rules:

- requires plugin install token,
- returns member/leader scoped data,
- hides fields based on clan membership and fight status.

### Plugin write API

Used by registered plugin clients only:

```text
POST /api/plugin/register
POST /api/plugin/heartbeat
POST /api/plugin/availability
POST /api/plugin/availability/{postId}/apply
POST /api/plugin/applications/{applicationId}/accept
POST /api/plugin/fights/{fightId}/events
POST /api/plugin/fights/{fightId}/complete-vote
```

Rules:

- requires install token,
- rate limited,
- validates schema and timestamps,
- leader endpoints require leader eligibility,
- event endpoints accept observations but do not immediately publish them as facts.

### Admin/moderation API

Not public and not part of the website:

```text
POST /api/admin/fights/{fightId}/hide
POST /api/admin/clans/{clanId}/verify
POST /api/admin/abuse/{reportId}/resolve
```

Rules:

- Azure Entra/GitHub operator only,
- separate auth path,
- not callable from the public website.

## Plugin registration

On first sync, plugin creates an install identity:

```text
install_id: random UUID generated locally
public_nonce: random
plugin_version
runelite_version
player_name
clan_name
observed_rank
```

Server returns a short-lived or rotatable install token.

Important:

- This does not prove a real RuneLite client.
- It gives us identity/rate-limiting handles.
- Suspicious installs can be throttled or revoked.

## Request authentication

For write APIs:

```text
Authorization: Bearer <install-token>
X-CWB-Install-Id: <install-id>
X-CWB-Request-Id: <uuid>
X-CWB-Timestamp: <unix-ms>
X-CWB-Plugin-Version: <version>
```

Server rejects:

- missing token,
- repeated request id,
- timestamp too far from server time,
- payload over size limit,
- invalid enum/string/world/timestamp values,
- endpoints inconsistent with observed role.

## Leader authorization

V1:

- plugin observes local RuneLite clan rank,
- backend records leader action as `plugin_observed_leader`,
- public UI labels clan as unverified unless clan is claimed/verified.

V2:

- clan claiming,
- Discord OAuth/bot verification,
- verified leader roster,
- leader actions require verified identity.

Leader action endpoints should require:

```text
observed_clan_id == action_clan_id
observed_rank >= configured_minimum
install has recent heartbeats
player not rate-limited/revoked
```

## Website cannot mess up data

Website is separated from write paths:

- Static Web App hosts frontend.
- Website reads only `/api/public/*` or static snapshots.
- No write tokens are shipped to the browser.
- CORS allows website origins only for read endpoints, but write security does not rely on CORS.
- Plugin write endpoints reject browser-like unauthenticated requests.

For higher traffic, public leaderboard/detail pages should read from generated static JSON snapshots:

```text
/public-data/leaderboard.json
/public-data/fights/{fightId}.json
/public-data/clans/{clanId}.json
```

The plugin write path updates Cosmos; a scheduled function/materializer updates public snapshots.

## Rate limiting strategy without paid API Management

Keep near-free by implementing app-level rate limiting using Cosmos/Storage counters and in-memory best-effort caching.

Buckets:

```text
install_id + endpoint
player_name + endpoint
clan_id + endpoint
source_ip prefix + endpoint
fight_id + event_type
```

Initial caps:

```text
heartbeat: 1/min/install
event batch: 1 every 5s/install during live fight
leader create/apply/accept: low, e.g. 20/hour/leader
public reads: cached/static where possible
```

## Telemetry integrity

Fight stats require corroboration.

Do not publish a kill/death/return from one client unless confidence rules allow it.

Evidence rules:

- prefer events observed by multiple clients,
- weight participants from confirmed clans higher than outsiders,
- detect impossible timelines,
- de-duplicate reports by event fingerprint,
- keep raw observations append-only,
- publish derived facts separately.

## Third-party players

Third-party players should be tracked as interaction entities:

```text
third_party_player_seen
third_party_damage_dealt
third_party_damage_taken
third_party_kill_or_death
```

They should affect confidence and interference metrics, but not automatically count toward either clan's win unless clearly associated later.

## High-traffic / low-latency plan

Near-free first:

- cache public responses,
- generate static snapshots for website,
- batch live telemetry events,
- avoid high-frequency polling,
- use Cosmos partition keys around clan/fight IDs,
- keep Functions stateless and small,
- use Event/Queue buffering later if write spikes hurt latency.

Scale-up path if free tier is abused/outgrown:

1. Add Azure Storage Queue for telemetry ingestion buffer.
2. Add scheduled/materializer Functions.
3. Add Front Door/Cloudflare caching only if needed and cost-approved.
4. Move hot public reads to static blob/SWA assets.
5. Add paid API Management only if app-level rate limiting is insufficient.

## Logging rules

Never log:

- install tokens,
- raw auth headers,
- exact upcoming rally notes/world fallback details,
- full request bodies by default.

Log minimally:

- request id,
- endpoint,
- status code,
- coarse latency,
- install/clan/fight IDs hashed if needed,
- rejection reason category.
