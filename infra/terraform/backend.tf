terraform {
  backend "azurerm" {
    resource_group_name  = "rg-cwb-tfstate"
    storage_account_name = "cwbtfstate4f070006f5"
    container_name       = "tfstate"
    key                  = "clan-war-board/dev.tfstate"
  }
}