param python_version string
param location string = resourceGroup().location

var eventgrid_name = 'python-worker-${python_version}-egt'

resource eventgrid 'Microsoft.EventGrid/topics@2023-12-15-preview' = {
  name: eventgrid_name
  location: location
  sku: {
    name: 'Basic'
  }
  kind: 'Azure'
}