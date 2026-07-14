output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "function_app_name" {
  value = azurerm_linux_function_app.api.name
}

output "function_app_default_hostname" {
  value = azurerm_linux_function_app.api.default_hostname
}

output "function_app_health_url" {
  value = "https://${azurerm_linux_function_app.api.default_hostname}/api/health"
}

output "static_web_app_name" {
  value = azurerm_static_web_app.web.name
}

output "static_web_app_default_hostname" {
  value = azurerm_static_web_app.web.default_host_name
}

output "cosmos_account_name" {
  value = azurerm_cosmosdb_account.main.name
}

output "cosmos_database_name" {
  value = azurerm_cosmosdb_sql_database.main.name
}

output "cosmos_endpoint" {
  value = azurerm_cosmosdb_account.main.endpoint
}

output "cosmos_primary_key" {
  value     = azurerm_cosmosdb_account.main.primary_key
  sensitive = true
}

output "static_web_app_api_key" {
  value     = azurerm_static_web_app.web.api_key
  sensitive = true
}
