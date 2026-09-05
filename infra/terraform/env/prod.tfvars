environment                = "prod"
location                   = "East US"
static_web_app_location    = "East US 2"
project_name               = "cwb"
cosmos_database_throughput = 400
monthly_budget_amount      = 10
budget_contact_emails      = []

tags = {
  AppName        = "ClanWarBoard"
  AppSlug        = "clan-war-board"
  Project        = "ClanWarBoard"
  Service        = "clan-war-board"
  ManagedBy      = "Terraform"
  DeployedBy     = "HermesAgent"
  DeploymentTool = "HermesAgent"
  IaC            = "Terraform"
  Repository     = "ItMeansBigMountain/clan-war-board-service"
  CostGuard      = "near-free"
}