# Clan War Board Service

Backend API and static leaderboard service for the Clan War Board RuneLite plugin.

This project is intentionally separate from the Plugin Hub-facing RuneLite plugin. The plugin stays in `projects/osrs-plugins/in-progress/ClanWarBoard`, while this service owns its own app code, docs, and Azure infrastructure.

## Goals

- Keep hosting free or near-free on Azure.
- Provide a backend API for Clan War Board.
- Start with static clan leaderboards so clans can compete for the top.
- Later add war proposals, leader acceptance, verified clans, and completed-war summaries.
- Explore Wise Old Man clan/group import when a clan already exists on WOM.
- Design security up front because public PvP/clan tools will attract abuse.

## Layout

```text
api/                  Azure Functions HTTP API and pure Python service code
infra/terraform/      Terraform IaC for free-tier Azure resources
docs/                 Cost, organization, security, and plugin-contract docs
tests/                Unit tests for API/service behavior
.github/workflows/    Separate infra and app deployment pipelines
```

## HTTP API

Azure Functions expose these routes beneath `/api`. Function-level Azure auth is anonymous; authenticated plugin routes enforce bearer sessions, capabilities, timestamps, nonces, expiry, and rate limits in application code.

### Public routes

| Method and route | Purpose |
| --- | --- |
| `GET /api/health` | Service/storage health and production-readiness metadata. |
| `GET /api/leaderboard` | Standings for plugin-registered clans. |
| `GET /api/challenge-system`, `GET /api/judging-system`, `GET /api/fight-setup/schema` | Public workflow, judging, and fight-term schemas. |
| `GET /api/clans[?q={query}]`, `GET /api/clans/{clanId}` | Registered-clan search and privacy-filtered profiles. |
| `GET /api/public/availability`, `GET /api/public/battles` | Open/scheduled availability and completed battles. |
| `GET /api/public/fights/{fightId}/summary` | Completed-fight terms, aggregate analytics, hotspots, and event timeline. |
| `GET /api/theme/assets` | Theme colors and any OSRS Wiki images resolved at request time. |

### Plugin routes

| Method and route | Required capability / result |
| --- | --- |
| `POST /api/plugin/register` | Validates installation/member data and issues a one-hour session. |
| `POST /api/plugin/session/rotate` | `member:read`; revokes/replaces the session. |
| `POST /api/plugin/availability` | `leader:write`; creates availability. |
| `GET|POST /api/plugin/challenges` | Reads involved challenges (`member:read`) or creates one (`challenge:write`). |
| `POST /api/plugin/challenges/{id}/actions` | `challenge:write`; accept/counter/reject/cancel. |
| `GET /api/plugin/me/metrics` | `member:read`; owner-only aggregates/events. |
| `POST /api/plugin/events/batch` | `telemetry:write`; validates/stores up to 50 fight events. |

Authenticated calls require `Authorization: Bearer …`, `X-CWB-Timestamp` within 300 seconds, and a previously unused UUID `X-CWB-Nonce`. Tokens are stored only by SHA-256 hash. Sessions allow 30 requests per rolling 60 seconds. Members receive `member:read`/`telemetry:write`; observed rank 100+ receives `leader:write`/`challenge:write`. This rank is RuneLite client-observed evidence, not Jagex-signed proof.

Registration accepts installation UUID, player/clan names, observed rank, plugin version, and privacy preference. Availability/challenge routes validate dates, durations, combat ranges, world, location, rules, and participant authority. Telemetry validates event type, clan, confirmed-fight world/window, numeric/location fields, and evidence enums; deterministic IDs make retries idempotent.

Public profiles show names only for opted-in members. Raw installation IDs and bearer tokens are not published. Live scheduled rows omit exact terms; completed summaries publish terms and detailed analysis. Owner metrics require the installation session.

## Service outbound dependencies

- **OSRS Wiki MediaWiki API:** `GET https://oldschool.runescape.wiki/api.php` from `/api/theme/assets` resolves images for Wilderness, Clan Wars, and Revenant Caves. Results are cached in memory for 24 hours; failures omit images without breaking theme metadata. No credentials are used.
- **Azure Cosmos DB:** when `STORAGE_BACKEND=cosmos`, the Azure SDK connects to configured clan/war containers. Endpoint/credential values come from environment configuration and must not be documented or committed.
- **Local fallback:** without Cosmos mode, process-local memory stores registrations, sessions, challenges, availability, and telemetry. Health reports `memory-local-only`; data is non-durable and unsuitable for production.

Wise Old Man appears only in planning documents; current service source does not call it.

## Product direction

The target product is a RuneLite-first clan competition network:

- leaders post fight availability,
- other leaders apply/accept,
- confirmed fight terms are locked by both leaders,
- plugin clients submit batched fight observations,
- service aggregates kills/deaths/returns/damage/third-party interference,
- plugin shows compact overview metrics,
- website shows detailed completed-fight analytics.

Planning docs:

```text
docs/product-architecture.md
docs/api-security-traffic-model.md
docs/api-contract.md
docs/runelite-plugin-ux.md
```

## Free-tier Azure target

```text
Azure Static Web Apps Free
Azure Functions Consumption
Azure Cosmos DB Free Tier
```

Cosmos DB must be created with `free_tier_enabled = true`; it cannot be toggled later.

## GitHub Actions pipelines

This repo is set up for two separate pipelines:

```text
.github/workflows/infra-terraform.yml  # Terraform plan/apply for Azure resources
.github/workflows/app-deploy.yml       # Tests and deploys API/web code
```

Both use GitHub OIDC against Azure. No `AZURE_CREDENTIALS` or Azure client secret is required for infra/app deployment.

## Local validation

The core service logic has no cloud dependency and can be tested locally:

```bash
python3 -m unittest discover -s tests -v
```

Azure Functions wiring is intentionally thin and wraps the pure Python API module.
