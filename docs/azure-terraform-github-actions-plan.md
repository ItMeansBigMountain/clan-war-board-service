# Azure Terraform + GitHub Actions Plan

## Goal

Give GitHub Actions secure Azure access for the Clan War Board service without storing an Azure password/client secret, then split the same repo into two pipelines:

1. **Infrastructure pipeline** — runs Terraform from `infra/` and changes Azure resources only after approval.
2. **Application pipeline** — builds/tests/deploys the API/web app into the already-created Azure resources, with its own approval gate.

## Existing Azure patterns observed

### Public `ItMeansBigMountain/az204` repo

I found the AZ-204 example on GitHub at:

```text
https://github.com/ItMeansBigMountain/az204
```

Important patterns from that repo:

- `.github/workflows/function-app-cicd.yml` deploys a Python Azure Function app from `labs/function_apps/app`.
- Function deployment uses a publish profile secret:

  ```yaml
  uses: Azure/functions-action@v1
  with:
    app-name: daily-portfolio-func
    package: labs/function_apps/app
    publish-profile: ${{ secrets.AZURE_FUNCTIONAPP_PUBLISH_PROFILE }}
    scm-do-build-during-deployment: true
    enable-oryx-build: true
  ```

- `.github/workflows/docker-acr-deploy.yml` uses `azure/login@v1` with:

  ```yaml
  creds: ${{ secrets.AZURE_CREDENTIALS }}
  ```

- The Docker workflow also uses ACR username/password secrets:

  ```yaml
  ACR_USERNAME
  ACR_PASSWORD
  ```

- Function app Terraform lives at `labs/function_apps/infra` and creates:
  - resource group
  - storage account
  - Linux consumption service plan `sku_name = "Y1"`
  - Application Insights
  - Cosmos DB account/database/container
  - Linux Function App

- Terraform variables mark sensitive values like subscription ID, SMTP password, and API keys as `sensitive = true`.
- Terraform outputs include function hostname and sensitive Cosmos key.

This confirms the style: separate app folders, path-filtered workflows, Azure secrets in GitHub Actions, Terraform infra dirs per lab/service, and publish-profile based app deploys.

### Local `projects/MusicAI` pattern

I also found the older Azure/Terraform pattern in `projects/MusicAI`:

- `simple-setup.md` used `az login`, then `az ad sp create-for-rbac --name "musicai-sp" --role contributor --scopes /subscriptions/$(az account show --query id -o tsv)`.
- GitHub Actions secrets expected there were:
  - `AZURE_CREDENTIALS`
  - `AZURE_SUBSCRIPTION_ID`
  - `AZURE_TENANT_ID`
  - `AZURE_CLIENT_ID`
  - `AZURE_CLIENT_SECRET`
- App/API secrets were also kept in GitHub Actions encrypted secrets.
- Terraform lived under `infra/terraform` and used `azurerm` with `subscription_id = var.subscription_id` in one provider file.
- The older deployment model combined infra/app deployment concepts around a simple push-to-main deploy.

For Clan War Board, keep the same practical style of path-filtered workflows and repo/environment variables/secrets, but modernize Azure auth to GitHub OIDC so we avoid storing `AZURE_CREDENTIALS` or `AZURE_CLIENT_SECRET` for Azure infra deploys. For app deploy, prefer OIDC + `az functionapp deployment source config-zip` over publish profiles unless Static Web Apps requires a deployment token.
## Recommended auth model: GitHub OIDC to Azure

Use GitHub Actions OpenID Connect (OIDC) with an Azure Microsoft Entra app registration/service principal. This is better than sharing `az login` browser state or storing `AZURE_CREDENTIALS` JSON because GitHub receives short-lived tokens only during an approved workflow run.

Do **not** copy long-lived Azure credentials into this repo.

When the user says **“pim up”**, start Azure CLI device-code login and return the Microsoft login URL/code so the user can authenticate/PIM-elevate interactively.

### What Hermes needs locally

For local/bootstrap work, Hermes can use your Azure CLI login if you authenticate on the machine/session where Hermes runs:

```bash
az login --use-device-code
az account set --subscription "<SUBSCRIPTION_ID_OR_NAME>"
az account show --query '{tenantId:tenantId, subscriptionId:id, name:name}' -o table
```

Do not paste tokens or credential JSON into chat. Device-code login is safer because you authenticate directly with Microsoft.

If `az` is not installed on the Hermes host, install Azure CLI first or run the bootstrap commands locally and commit only non-secret outputs/config.

## One-time Azure bootstrap for GitHub Actions

Inputs needed:

```text
AZURE_TENANT_ID
AZURE_SUBSCRIPTION_ID
GITHUB_OWNER = ItMeansBigMountain
GITHUB_REPO = clan-war-board-service
```

Create an app registration/service principal:

```bash
APP_NAME="gh-cwb-terraform"
SUBSCRIPTION_ID="<subscription-id>"

APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
az ad sp create --id "$APP_ID"

SCOPE="/subscriptions/$SUBSCRIPTION_ID"
az role assignment create \
  --assignee "$APP_ID" \
  --role Contributor \
  --scope "$SCOPE"
```

For tighter least privilege later, scope this to the Clan War Board resource group after bootstrap instead of the whole subscription.

### Federated credentials

Create separate federated credentials for separate GitHub environments. This lets GitHub environment approvals become part of the trust boundary.

```bash
OWNER="ItMeansBigMountain"
REPO="clan-war-board-service"

az ad app federated-credential create --id "$APP_ID" --parameters "{
  \"name\": \"github-cwb-infra-dev\",
  \"issuer\": \"https://token.actions.githubusercontent.com\",
  \"subject\": \"repo:${OWNER}/${REPO}:environment:infra-dev\",
  \"audiences\": [\"api://AzureADTokenExchange\"]
}"

az ad app federated-credential create --id "$APP_ID" --parameters "{
  \"name\": \"github-cwb-app-dev\",
  \"issuer\": \"https://token.actions.githubusercontent.com\",
  \"subject\": \"repo:${OWNER}/${REPO}:environment:app-dev\",
  \"audiences\": [\"api://AzureADTokenExchange\"]
}"
```

For production, add separate environments and credentials:

```text
infra-prod
app-prod
```

## GitHub repository variables/secrets

Use repository or environment **variables** for non-secrets:

```text
AZURE_CLIENT_ID       = app registration client ID
AZURE_TENANT_ID       = tenant ID
AZURE_SUBSCRIPTION_ID = subscription ID
```

With OIDC, no client secret is required.

Use GitHub **Environments** for approval gates:

```text
infra-dev
app-dev
infra-prod
app-prod
```

Set required reviewers on `infra-prod` and `app-prod`. Optionally also require reviewers on dev while we are learning cost behavior.

## Terraform state

Terraform needs remote state. Recommended Azure backend:

```text
resource group: rg-cwb-tfstate
storage account: <globally unique>
container: tfstate
key: clan-war-board/dev.tfstate
```

Bootstrap the state backend once with Azure CLI or a tiny one-time script. Keep it outside the app resource group so accidental app teardown does not delete state.

Example backend block:

```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-cwb-tfstate"
    storage_account_name = "<tfstate-storage-account>"
    container_name       = "tfstate"
    key                  = "clan-war-board/dev.tfstate"
    use_oidc             = true
  }
}
```

Provider auth:

```hcl
provider "azurerm" {
  features {}
  use_oidc = true
}
```

Workflow env:

```yaml
env:
  ARM_USE_OIDC: true
  ARM_CLIENT_ID: ${{ vars.AZURE_CLIENT_ID }}
  ARM_TENANT_ID: ${{ vars.AZURE_TENANT_ID }}
  ARM_SUBSCRIPTION_ID: ${{ vars.AZURE_SUBSCRIPTION_ID }}
```

## Two pipelines in the same repo

GitHub Actions separates pipelines by separate files in `.github/workflows/`.

Recommended files:

```text
.github/workflows/infra-terraform.yml
.github/workflows/app-deploy.yml
```

### Pipeline 1: infrastructure

Triggers:

- PRs touching `infra/**` run `terraform fmt`, `validate`, and `plan`.
- Manual `workflow_dispatch` applies after environment approval.
- Push to main touching `infra/**` can run plan only, not apply.

Important gate:

```yaml
environment: infra-dev
```

or for prod:

```yaml
environment: infra-prod
```

### Pipeline 2: application deployment

Triggers:

- PRs touching `api/**`, `web/**`, or tests run build/tests.
- Push to main touching app paths deploys to dev after `app-dev` approval.
- Manual dispatch can deploy a selected environment.

Important gate:

```yaml
environment: app-dev
```

The app pipeline should not run Terraform. It should only deploy to resource names exposed by Terraform outputs or saved environment variables.

## Example infra workflow

```yaml
name: infra-terraform

on:
  pull_request:
    paths:
      - 'infra/**'
      - '.github/workflows/infra-terraform.yml'
  push:
    branches: [main]
    paths:
      - 'infra/**'
      - '.github/workflows/infra-terraform.yml'
  workflow_dispatch:
    inputs:
      environment:
        description: GitHub environment to deploy
        type: choice
        options: [infra-dev, infra-prod]
        default: infra-dev
      apply:
        description: Apply Terraform changes
        type: boolean
        default: false

permissions:
  id-token: write
  contents: read
  pull-requests: write

env:
  ARM_USE_OIDC: true
  ARM_CLIENT_ID: ${{ vars.AZURE_CLIENT_ID }}
  ARM_TENANT_ID: ${{ vars.AZURE_TENANT_ID }}
  ARM_SUBSCRIPTION_ID: ${{ vars.AZURE_SUBSCRIPTION_ID }}

jobs:
  terraform:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'infra-dev' }}
    defaults:
      run:
        working-directory: infra
    steps:
      - uses: actions/checkout@v4

      - uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}

      - uses: hashicorp/setup-terraform@v3

      - run: terraform fmt -check -recursive
      - run: terraform init
      - run: terraform validate
      - run: terraform plan -out=tfplan

      - name: Terraform apply
        if: github.event_name == 'workflow_dispatch' && github.event.inputs.apply == 'true'
        run: terraform apply -auto-approve tfplan
```

## Example app deployment workflow

```yaml
name: app-deploy

on:
  pull_request:
    paths:
      - 'api/**'
      - 'web/**'
      - 'tests/**'
      - '.github/workflows/app-deploy.yml'
  push:
    branches: [main]
    paths:
      - 'api/**'
      - 'web/**'
      - 'tests/**'
      - '.github/workflows/app-deploy.yml'
  workflow_dispatch:
    inputs:
      environment:
        description: GitHub environment to deploy
        type: choice
        options: [app-dev, app-prod]
        default: app-dev

permissions:
  id-token: write
  contents: read

env:
  AZURE_FUNCTIONAPP_NAME: ${{ vars.AZURE_FUNCTIONAPP_NAME }}
  AZURE_STATIC_WEB_APP_NAME: ${{ vars.AZURE_STATIC_WEB_APP_NAME }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r api/requirements.txt
      - run: python -m unittest discover -s tests -v

  deploy-api:
    needs: test
    if: github.event_name != 'pull_request'
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'app-dev' }}
    steps:
      - uses: actions/checkout@v4

      - uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Package API
        run: |
          cd api
          zip -r ../api.zip .

      - name: Deploy Azure Function app
        run: |
          az functionapp deployment source config-zip \
            --name "$AZURE_FUNCTIONAPP_NAME" \
            --resource-group "${{ vars.AZURE_RESOURCE_GROUP }}" \
            --src api.zip
```

## Approval gate model

Use GitHub Environments as the approval mechanism.

Suggested setup:

| Environment | Purpose | Required reviewers |
|---|---|---|
| infra-dev | deploy/update dev Azure resources | optional during setup; recommended on |
| app-dev | deploy app to dev Azure resources | optional during setup; recommended on |
| infra-prod | production infra changes | required |
| app-prod | production app deploys | required |

OIDC federated credentials should match each environment subject exactly:

```text
repo:ItMeansBigMountain/clan-war-board-service:environment:infra-dev
repo:ItMeansBigMountain/clan-war-board-service:environment:app-dev
repo:ItMeansBigMountain/clan-war-board-service:environment:infra-prod
repo:ItMeansBigMountain/clan-war-board-service:environment:app-prod
```

## How this maps to Clan War Board

Repo layout:

```text
clan-war-board-service/
  api/                      # app pipeline
  web/                      # app pipeline
  infra/                    # infra pipeline
  tests/                    # app pipeline validation
  .github/workflows/
    infra-terraform.yml
    app-deploy.yml
```

Path filters keep unrelated changes from running the wrong pipeline.

Terraform creates/updates:

```text
resource group
storage account
function app
static web app
cosmos account/database/containers
budget alerts
```

App pipeline deploys only:

```text
api code to Function App
web build to Static Web App
```

## Practical bootstrap order

1. Install/login Azure CLI locally or on Hermes host.
2. Confirm subscription and tenant.
3. Create Terraform state resource group/storage/container.
4. Create app registration/service principal.
5. Add federated credentials for GitHub environments.
6. Add GitHub environments + required reviewers.
7. Add GitHub environment variables.
8. Add Terraform files under `infra/`.
9. Add `infra-terraform.yml`; run plan first.
10. Manually approve/apply dev infra.
11. Add app deploy workflow.
12. Deploy API to created Function App.
13. Verify `/api/health` live before wiring RuneLite plugin online sync.
