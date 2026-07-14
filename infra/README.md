# Terraform Infra

Terraform IaC for the Clan War Board Azure service. This replaces the earlier Bicep scaffold so it matches the user's AZ-204 Terraform/GitHub Actions style.

## Target Azure shape

Near-free MVP resources:

- Resource group
- Azure Storage Account for Functions runtime
- Azure Linux Function App on Consumption plan (`Y1`)
- Application Insights with low sampling
- Azure Cosmos DB account with `free_tier_enabled = true`
- Cosmos SQL database with shared throughput capped at `400–1000` RU/s
- Cosmos containers: `clans`, `wars`, `summaries`
- Azure Static Web App Free
- Optional resource-group budget alerts

## Cost guardrails

- Cosmos DB free tier must be created correctly on the first apply.
- Keep `cosmos_database_throughput <= 1000`.
- Do not switch the Function App plan away from `Y1` for MVP.
- Do not add Front Door, App Gateway, AKS, VMs, or Premium Functions.
- Keep `budget_contact_emails` populated before public launch.

## Local commands after `pim up`

```bash
cd infra/terraform
terraform fmt -recursive
terraform init \
  -backend-config="resource_group_name=rg-cwb-tfstate" \
  -backend-config="storage_account_name=<tfstate-storage-account>" \
  -backend-config="container_name=tfstate" \
  -backend-config="key=clan-war-board/dev.tfstate" \
  -backend-config="use_oidc=true"
terraform validate
terraform plan -var-file=env/dev.tfvars -var="azure_subscription_id=$(az account show --query id -o tsv)"
```

## GitHub Actions

The repo should use two workflows:

- `.github/workflows/infra-terraform.yml` for Terraform plan/apply.
- `.github/workflows/app-deploy.yml` for API/web deployment.

Both authenticate to Azure with GitHub OIDC and environment approval gates.
