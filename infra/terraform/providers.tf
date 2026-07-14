provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
  use_oidc        = true
}
