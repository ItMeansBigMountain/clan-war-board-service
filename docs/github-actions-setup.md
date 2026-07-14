# GitHub Actions Setup Checklist

## Required GitHub Environments

Create these environments in the service repo:

```text
infra-dev
app-dev
infra-prod
app-prod
```

Recommended gates:

- Require approval for `infra-dev` while cost behavior is being verified.
- Require approval for `infra-prod` and `app-prod` always.

## Required GitHub Variables

Set these at the repository level or per environment:

```text
AZURE_CLIENT_ID
AZURE_TENANT_ID
AZURE_SUBSCRIPTION_ID
TFSTATE_RESOURCE_GROUP
TFSTATE_STORAGE_ACCOUNT
TFSTATE_CONTAINER
AZURE_RESOURCE_GROUP
AZURE_FUNCTIONAPP_NAME
AZURE_STATIC_WEB_APP_NAME
```

Notes:

- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` are non-secret IDs used for OIDC.
- `AZURE_RESOURCE_GROUP`, `AZURE_FUNCTIONAPP_NAME`, and `AZURE_STATIC_WEB_APP_NAME` should match Terraform outputs for the target environment.
- `TFSTATE_*` points at the Terraform backend storage account/container.

## Required GitHub Secrets

Azure deployment auth itself should not need a client secret.

Optional app/web secrets:

```text
AZURE_STATIC_WEB_APPS_API_TOKEN  # only needed once web deployment exists
```

Do not add old-style Azure infra secrets unless we intentionally fall back:

```text
AZURE_CREDENTIALS
AZURE_CLIENT_SECRET
```

## Azure OIDC Federated Credentials

Create one federated credential per environment subject:

```text
repo:ItMeansBigMountain/clan-war-board-service:environment:infra-dev
repo:ItMeansBigMountain/clan-war-board-service:environment:app-dev
repo:ItMeansBigMountain/clan-war-board-service:environment:infra-prod
repo:ItMeansBigMountain/clan-war-board-service:environment:app-prod
```

## `pim up` flow

When the user says `pim up`, start:

```bash
az login --use-device-code
```

Give the user the device login URL and code. After login/PIM elevation, verify:

```bash
az account show --query '{tenantId:tenantId, subscriptionId:id, name:name}' -o table
```

Then bootstrap or update Azure/GitHub settings.
