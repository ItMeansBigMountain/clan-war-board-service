locals {
  resource_group_name = var.resource_group_name != "" ? var.resource_group_name : "rg-${var.project_name}-${var.environment}"
  name_prefix         = lower("${var.project_name}-${var.environment}")
  merged_tags = merge(var.tags, {
    Environment = var.environment
    Service     = "clan-war-board"
  })
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_resource_group" "main" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.merged_tags
}

resource "azurerm_cosmosdb_account" "main" {
  name                = "cosmos-${local.name_prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"
  free_tier_enabled   = true

  minimal_tls_version                = "Tls12"
  public_network_access_enabled      = true
  local_authentication_enabled       = true
  automatic_failover_enabled         = false
  multiple_write_locations_enabled   = false
  access_key_metadata_writes_enabled = false

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.main.location
    failover_priority = 0
    zone_redundant    = false
  }

  tags = local.merged_tags
}

resource "azurerm_cosmosdb_sql_database" "main" {
  name                = "clan-war-board"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  throughput          = var.cosmos_database_throughput
}

resource "azurerm_cosmosdb_sql_container" "clans" {
  name                = "clans"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/normalizedName"]
}

resource "azurerm_cosmosdb_sql_container" "wars" {
  name                = "wars"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/clanPairKey"]
}

resource "azurerm_cosmosdb_sql_container" "summaries" {
  name                = "summaries"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/warId"]
}

resource "azurerm_static_web_app" "web" {
  name                = "stapp-${local.name_prefix}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.static_web_app_location
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.merged_tags
}

resource "azurerm_consumption_budget_resource_group" "main" {
  count             = length(var.budget_contact_emails) > 0 ? 1 : 0
  name              = "budget-${local.name_prefix}"
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.monthly_budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00'Z'", timestamp())
  }

  notification {
    enabled        = true
    threshold      = 50
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = var.budget_contact_emails
  }

  notification {
    enabled        = true
    threshold      = 90
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = var.budget_contact_emails
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}
