# Azure Service Account

## Purpose

The Azure service account is the non-human deployment identity for Hermes-managed Azure/Terraform work.

It is used by:

- GitHub Actions via OIDC federation.
- Local Hermes CLI sessions via a service-principal login helper.
- Terraform against the shared remote state storage account.

## Cost

Creating and using this Entra application/service principal is free. Role assignments and federated credentials are free. The local service-principal credential itself is free.

No additional paid Azure resources are required for this identity.

## Current identity

```text
Display name: hermes-azure-terraform-deployer
Client ID: aa6a45f2-3486-4bff-8ae5-c97e596b3e1c
Tenant ID: 8b5e3e1a-e763-48c5-accf-346b8eebaaf5
Subscription ID: 4f070006-f5e7-471d-a859-b15a2a8ee406
```

## Roles

```text
Contributor                    /subscriptions/4f070006-f5e7-471d-a859-b15a2a8ee406
Storage Blob Data Contributor  /subscriptions/4f070006-f5e7-471d-a859-b15a2a8ee406/resourceGroups/rg-cwb-tfstate/providers/Microsoft.Storage/storageAccounts/cwbtfstate4f070006f5
```

The subscription-level Contributor role lets the identity deploy future Azure/Terraform projects in this subscription. The storage role lets Terraform read/write remote state in the shared state account.

Do not grant Owner by default. If a future Terraform project needs role assignments, prefer adding a narrow extra role intentionally and documenting why.

## GitHub OIDC federated credentials

The same service account trusts these GitHub environment subjects:

```text
repo:ItMeansBigMountain/clan-war-board-service:environment:infra-dev
repo:ItMeansBigMountain/clan-war-board-service:environment:app-dev
repo:ItMeansBigMountain/clan-war-board-service:environment:infra-prod
repo:ItMeansBigMountain/clan-war-board-service:environment:app-prod
```

GitHub Actions should keep using OIDC. Do not add a client secret to GitHub Actions unless there is a hard blocker.

## Local persistent Hermes login

A local service-principal credential was created outside the repo at:

```text
/opt/data/secrets/hermes-azure-terraform-deployer.env
```

Permissions:

```text
600
```

The helper script is:

```text
/opt/data/scripts/azure_sp_login.sh
```

Use it before local Azure/Terraform work:

```bash
/opt/data/scripts/azure_sp_login.sh
```

The script logs in with the service principal and selects the `oyamaProductions` subscription.

## Secret handling

Never commit or print the local `.env` file. It contains `AZURE_CLIENT_SECRET`.

If the secret is exposed, rotate it:

```bash
az ad app credential reset --id aa6a45f2-3486-4bff-8ae5-c97e596b3e1c --append --display-name hermes-local-cli-YYYYMMDD --years 1
```

Then update the local secret file and re-test:

```bash
/opt/data/scripts/azure_sp_login.sh
```

## Cost guardrail

This identity can create resources because it has Contributor. Before applying any future Terraform project:

1. Prefer Static Web Apps Free / serverless/no-quota resources.
2. Avoid VMs, AKS, Front Door, App Gateway, Premium Functions, paid App Service plans, and high-volume telemetry.
3. Include explicit budgets/alerts where possible.
4. Run `terraform plan` before `terraform apply`.
5. Keep prod applies behind GitHub environment approval.
