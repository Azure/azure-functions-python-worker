param python_version string
param location string = resourceGroup().location


var serviceBusNamespaceName = 'python-worker-${python_version}-sbns'

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-01-01-preview' = {
  name: serviceBusNamespaceName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {}
}

