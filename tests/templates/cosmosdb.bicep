param python_version string
param location string = resourceGroup().location

var cosmosdb_name = 'python-worker-${python_version}-cdb'

resource cosmosdb 'Microsoft.DocumentDB/databaseAccounts@2022-08-15' = {
  name: cosmosdb_name
  kind: 'GlobalDocumentDB'
  location: location
  properties: {
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    apiProperties: {}
    capabilities: [ { name: 'EnableServerless' } ]
  }
}
