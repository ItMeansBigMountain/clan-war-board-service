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

## MVP API

Current scaffold:

```text
GET /api/health
GET /api/leaderboard
GET /api/clans/{clanId}
```

The leaderboard is static/sample-backed until Cosmos DB is provisioned and connected.

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
