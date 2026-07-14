# Clan War Board Service — Azure Organization and Cost Plan

## Decision: service owns its infra

Keep infrastructure code **inside the service project**, not as a separate top-level infra project.

Recommended layout:

```text
projects/osrs-plugins/
  in-progress/ClanWarBoard/                       # RuneLite plugin only / Plugin Hub-facing
  services/
    clan-war-board-service/                       # separate backend/service project
      api/                                        # Azure Functions API
      web/                                        # optional Static Web Apps frontend
      infra/terraform/                            # Terraform for this service only
      docs/
        azure-cost-and-organization-plan.md       # this planning doc
        api.md
        privacy.md
        plugin-contract.md
```

This keeps Plugin Hub PR readiness clean: the RuneLite plugin repo does not contain cloud deployment code, secrets, or Azure-specific files. The service repo owns its app code and deployment IaC together.

Suggested future GitHub repo:

```text
ItMeansBigMountain/clan-war-board-service
```

Then the HeRmEz workspace can track it as a submodule at:

```text
projects/osrs-plugins/services/clan-war-board-service
```

## Recommended near-free Azure architecture

For the MVP, use:

```text
Azure Static Web Apps Free
Azure Functions Consumption Plan
Azure Cosmos DB Free Tier
```

### Components

| Component | Purpose | Why |
|---|---|---|
| Azure Static Web Apps Free | Optional public/admin site | Free hosting, SSL, custom domain support, GitHub deployment |
| Azure Functions Consumption | HTTPS API for plugin/service | Serverless, no always-on VM/App Service plan |
| Azure Cosmos DB Free Tier | Persistent clans/wars/acceptances data | Lifetime free allowance if explicitly enabled at creation |
| Azure Storage Account | Required by Functions | Small but not part of Functions free grant; keep minimal |
| Application Insights | Optional lightweight telemetry | Useful, but can generate cost if noisy |

## Cost analysis

### Known free allowances from current Microsoft docs/pricing pages

#### Azure Cosmos DB Free Tier

Microsoft Learn states Cosmos DB free tier provides, for the lifetime of the account:

```text
1000 RU/s free
25 GB storage free
```

Important constraints:

- Free tier must be enabled when the account is created.
- It cannot be enabled later.
- Only one Cosmos DB free-tier account is allowed per Azure subscription.
- Free tier is not available for serverless Cosmos DB accounts.
- Usage above 1000 RU/s or 25 GB is billed normally.

#### Azure Functions Consumption

Azure Functions Consumption includes a monthly free grant:

```text
1,000,000 executions/month
400,000 GB-s/month
```

Important constraints:

- The Functions storage account is not included in the Functions free grant.
- Network/bandwidth/storage charges can still apply.
- Avoid Premium/Flex Always Ready for MVP because those can add baseline costs.

#### Azure Static Web Apps Free

Azure Static Web Apps Free includes:

```text
Free static web hosting
SSL certificate
2 custom domains per app
100 GB included bandwidth per subscription
0.50 GB included storage
0.25 GB max deployment size per app
```

Static Web Apps can use Azure Functions APIs; function usage follows Azure Functions consumption pricing/free grants.

### Expected MVP usage

Assumptions for early Clan War Board MVP:

```text
100 clans
2,000 monthly active plugin users
20,000 API requests/day average
600,000 API requests/month
Small JSON documents, mostly reads/lists
No live location streaming
No high-frequency polling
```

Under this model:

| Meter | Estimate | Free allowance | Expected bill |
|---|---:|---:|---:|
| Static Web Apps bandwidth | likely < 100 GB/month | 100 GB/month | $0 |
| Functions executions | ~600k/month | 1M/month | $0 |
| Functions GB-s | tiny JSON API, likely below 400k GB-s | 400k GB-s/month | $0 |
| Cosmos DB throughput | provision 1000 RU/s shared DB | 1000 RU/s | $0 |
| Cosmos DB storage | likely < 1 GB | 25 GB | $0 |
| Storage account for Functions | logs/package/state | not included | low cents to small dollars if kept clean |
| Application Insights | optional | can incur cost | $0 if disabled/minimal; small if enabled |

Likely MVP monthly cost if configured carefully:

```text
$0 to a few dollars/month
```

The main risk is accidental configuration, not normal MVP traffic.

### Larger community scenario

Assumptions:

```text
25,000 monthly active plugin users
250,000 API requests/day
7.5M API requests/month
More public leaderboard traffic
More war history reads
```

Risk areas:

- Functions executions exceed 1M/month.
- Cosmos DB 1000 RU/s may be too low if reads are inefficient or polling is too frequent.
- Public web bandwidth can exceed 100 GB/month if pages/assets become popular.
- App Insights logs can become expensive if every plugin request logs full payloads.

Expected cost shape:

```text
Still modest if APIs are cached and polling is restrained, but no longer guaranteed free.
```

Before scaling, add:

- server-side caching for public leaderboard responses
- client polling limits
- ETags / `If-None-Match`
- CDN/static snapshots for public pages
- strict log sampling
- budget alerts

## Cost-control rules

Hard rules for the first deployment:

1. Use a dedicated Azure resource group:

   ```text
   rg-clan-war-board-dev
   ```

2. Create a budget alert immediately, e.g.:

   ```text
   $5/month warning
   $10/month critical
   ```

3. Use only:

   ```text
   Static Web Apps Free
   Functions Consumption
   Cosmos DB Free Tier with enableFreeTier=true
   ```

4. Do **not** create:

   ```text
   VM
   App Service paid plan
   Premium Functions
   Front Door
   Application Gateway
   Azure Kubernetes Service
   Cosmos DB multi-region writes
   Dedicated Cosmos container throughput above free allowance
   ```

5. Disable or minimize Application Insights until needed.

6. Keep API polling conservative:

   ```text
   manual refresh by default
   no per-tick API calls
   no live player location streaming
   minimum background refresh interval >= 5 minutes if enabled
   ```

7. Store only low-volume documents:

   ```text
   clans
   wars
   acceptances
   summaries
   public leaderboard snapshots
   ```

8. Never store secrets in repo or plugin config.

## Data model and privacy fit for Cosmos DB

Cosmos DB works for v1 because the data can be document-shaped.

Recommended containers for MVP:

```text
clans      partition key: /normalizedName
wars       partition key: /clanPairKey
summaries  partition key: /warId
```

`wars` documents can include participant/acceptance state directly for v1:

```json
{
  "id": "war_...",
  "type": "war",
  "clanPairKey": "trapiistan:rival-clan",
  "creatorClan": "TRAPISTAN",
  "opponentClan": "Rival Clan",
  "status": "PROPOSED",
  "termsHash": "...",
  "visibility": "CLAN_ONLY",
  "startTime": "...",
  "world": "330",
  "hotspot": "Lava Dragons",
  "rules": "Multi only. Returns allowed.",
  "acceptedBy": null,
  "createdAt": "...",
  "updatedAt": "..."
}
```

Privacy defaults:

| Audience | Can see before war |
|---|---|
| Public | clan names, broad status/category only |
| Clan members | date/time, world, hotspot, rules |
| Clan leaders | drafts, proposals, accept/edit/cancel controls |

Exact world/hotspot/time should never be public by default.

## Backend/API plan

Initial API endpoints:

```text
GET  /api/health
POST /api/session
GET  /api/clans/{clan}/wars
POST /api/wars
PATCH /api/wars/{warId}
POST /api/wars/{warId}/propose
POST /api/wars/{warId}/accept
POST /api/wars/{warId}/cancel
POST /api/wars/{warId}/complete
GET  /api/public/wars
GET  /api/public/leaderboard
```

`POST /api/session` receives plugin-observed identity data:

```json
{
  "playerName": "Oyama",
  "clanName": "TRAPISTAN",
  "rankValue": 100,
  "pluginVersion": "..."
}
```

Plugin Hub warning must disclose this before online sync is enabled.

## Authentication/verification plan

V1:

- Plugin detects local clan rank.
- Backend records actions as plugin-submitted.
- Clans are marked unverified unless claimed.
- Good enough for MVP/community testing.

V2:

- Add clan claiming.
- Add Discord OAuth/bot role verification.
- Add verified clan badge.
- Require verified leader accounts for public/global leaderboard authority.

## Deployment/IaC plan

Use Terraform inside the service repo:

```text
services/clan-war-board-service/infra/terraform/
  versions.tf
  providers.tf
  main.tf
  variables.tf
  outputs.tf
  env/dev.tfvars
  env/prod.tfvars
  README.md
```

Terraform creates:

```text
resource group reference
Static Web App Free
Function App Consumption
Storage Account for Functions
Cosmos DB account with enableFreeTier=true
Cosmos SQL database with shared throughput <= 1000 RU/s
Cosmos containers
optional budget alert resources
```

## Next steps

1. Remove/migrate any old top-level infra-only plan once this service layout is adopted.
2. Create `services/clan-war-board-service` as a standalone service project/repo.
3. Scaffold `api/`, `web/`, `infra/`, and `docs/`.
4. Add Bicep for the near-free Azure stack with explicit free-tier settings.
5. Implement `GET /api/health` locally.
6. Add budget alert docs and deployment checklist.
7. Only after service skeleton exists, add `Enable Online Sync` to RuneLite plugin.
