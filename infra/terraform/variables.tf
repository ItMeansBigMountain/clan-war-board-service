variable "azure_subscription_id" {
  type        = string
  description = "Azure subscription ID used for this deployment."
  sensitive   = true
}

variable "environment" {
  type        = string
  description = "Deployment environment name."
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "location" {
  type        = string
  description = "Primary Azure region for resources."
  default     = "East US"
}

variable "static_web_app_location" {
  type        = string
  description = "Azure Static Web Apps region. Must be one of the regions supported by Microsoft.Web/staticSites."
  default     = "East US 2"
}

variable "project_name" {
  type        = string
  description = "Short project slug used in Azure resource names."
  default     = "cwb"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for Clan War Board resources."
  default     = ""
}

variable "cosmos_database_throughput" {
  type        = number
  description = "Shared Cosmos DB SQL database throughput. Keep <= 1000 RU/s for free-tier safety."
  default     = 400

  validation {
    condition     = var.cosmos_database_throughput >= 400 && var.cosmos_database_throughput <= 1000
    error_message = "cosmos_database_throughput must stay between 400 and 1000 RU/s."
  }
}

variable "app_insights_sampling_percentage" {
  type        = number
  description = "Application Insights sampling percentage. Keep low to avoid telemetry cost spikes."
  default     = 10
}

variable "monthly_budget_amount" {
  type        = number
  description = "Monthly budget amount in USD for this resource group."
  default     = 10
}

variable "budget_contact_emails" {
  type        = list(string)
  description = "Email recipients for Azure budget alerts. Empty list disables budget resource."
  default     = []
}

variable "tags" {
  type        = map(string)
  description = "Common tags applied to resources."
  default = {
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
}
