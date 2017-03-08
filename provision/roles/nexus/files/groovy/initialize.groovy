import groovy.json.JsonSlurper

// cleanup
if (repository.getRepositoryManager().get('maven-public') != null) {
  repository.getRepositoryManager().delete('maven-public')
}
if (repository.getRepositoryManager().get('maven-releases') != null) {
  repository.getRepositoryManager().delete('maven-releases')
}
if (repository.getRepositoryManager().get('maven-snapshots') != null) {
  repository.getRepositoryManager().delete('maven-snapshots')
}
if (repository.getRepositoryManager().get('maven-central') != null) {
  repository.getRepositoryManager().delete('maven-central')
}
if (repository.getRepositoryManager().get('nuget-hosted') != null) {
  repository.getRepositoryManager().delete('nuget-hosted')
}
if (repository.getRepositoryManager().get('nuget.org-proxy') != null) {
  repository.getRepositoryManager().delete('nuget.org-proxy')
}
if (repository.getRepositoryManager().get('nuget-group') != null) {
  repository.getRepositoryManager().delete('nuget-group')
}
