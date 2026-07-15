output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "static_web_app_name" {
  value = azurerm_static_web_app.web.name
}

output "static_web_app_default_host_name" {
  value = azurerm_static_web_app.web.default_host_name
}

output "cosmos_account_name" {
  value = azurerm_cosmosdb_account.main.name
}

output "cosmos_endpoint" {
  value = azurerm_cosmosdb_account.main.endpoint
}

output "cosmos_database_name" {
  value = azurerm_cosmosdb_sql_database.main.name
}

output "cosmos_clans_container" {
  value = azurerm_cosmosdb_sql_container.clans.name
}

output "cosmos_wars_container" {
  value = azurerm_cosmosdb_sql_container.wars.name
}

output "cosmos_summaries_container" {
  value = azurerm_cosmosdb_sql_container.summaries.name
}
