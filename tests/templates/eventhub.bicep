param python_version string
param location string = resourceGroup().location

var eventhubname = 'python-worker-${python_version}-ehns'

resource eventhub 'Microsoft.EventHub/namespaces@2022-10-01-preview' = {
  name: eventhubname
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
}
