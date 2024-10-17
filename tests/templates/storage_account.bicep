param location string = resourceGroup().location
param python_version string

var storage_account_name = 'pythonworker${python_version}sa'

resource storageAccount_input 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storage_account_name
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
    accessTier: 'Hot'
    publicNetworkAccess: 'Enabled'
    dnsEndpointType: 'Standard'
    allowBlobPublicAccess: true
    minimumTlsVersion: 'TLS1_2'
    allowSharedKeyAccess: true
  }
}
