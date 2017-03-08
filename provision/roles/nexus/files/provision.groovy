import org.sonatype.nexus.blobstore.api.BlobStoreManager
import org.sonatype.nexus.repository.maven.LayoutPolicy
import org.sonatype.nexus.repository.maven.VersionPolicy
import org.sonatype.nexus.repository.storage.WritePolicy

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

// maven
repository.createMavenHosted('maven-releases', BlobStoreManager.DEFAULT_BLOBSTORE_NAME, true, VersionPolicy.RELEASE, WritePolicy.ALLOW_ONCE, LayoutPolicy.STRICT)
repository.createMavenHosted('maven-snapshot', BlobStoreManager.DEFAULT_BLOBSTORE_NAME, true, VersionPolicy.SNAPSHOT, WritePolicy.ALLOW, LayoutPolicy.STRICT)
repository.createMavenProxy('maven-central', 'https://jcenter.bintray.com/', BlobStoreManager.DEFAULT_BLOBSTORE_NAME, true, VersionPolicy.RELEASE, LayoutPolicy.STRICT)
repository.createMavenGroup('maven-public', ['maven-releases', 'maven-snapshot', 'maven-central'])

// docker
repository.createDockerHosted('docker-releases', 5001, 0)
repository.createDockerHosted('docker-snapshot', 5002, 0)
repository.createDockerProxy('docker-central', 'https://registry-1.docker.io/', 'REGISTRY', '', 0, 0)
repository.createDockerGroup('docker-public', 5000, 0, ['docker-releases','docker-snapshot','docker-central'])

// npm
repository.createNpmHosted('npm-releases')
repository.createNpmHosted('npm-snapshot')
repository.createNpmProxy('npm-central', 'https://registry.npm.taobao.org/')
repository.createNpmGroup('npm-public', ['npm-releases', 'npm-snapshot', 'npm-central'])

// bower
repository.createBowerHosted('bower-releases')
repository.createBowerHosted('bower-snapshot')
repository.createBowerProxy('bower-central', 'http://bower.herokuapp.com')
repository.createBowerGroup('bower-public', ['bower-releases','bower-snapshot','bower-central'])

// nuget
repository.createNugetHosted('nuget-releases')
repository.createNugetHosted('nuget-snapshot')
repository.createNugetProxy('nuget-central', 'https://www.nuget.org/api/v2/')
repository.createNugetGroup('nuget-public', ['nuget-releases','nuget-snapshot','nuget-central'])

// pypi
repository.createRepository(repository.createHosted('pypi-releases', 'pypi-hosted'))
repository.createRepository(repository.createHosted('pypi-snapshot', 'pypi-hosted'))
repository.createRepository(repository.createProxy('pypi-central', 'pypi-proxy', 'http://mirrors.aliyun.com/pypi/'))
repository.createRepository(repository.createGroup('pypi-public', 'pypi-group', BlobStoreManager.DEFAULT_BLOBSTORE_NAME, 'pypi-releases', 'pypi-snapshot', 'pypi-central'))

// rubygems
repository.createRepository(repository.createHosted('rubygems-releases', 'rubygems-hosted'))
repository.createRepository(repository.createHosted('rubygems-snapshot', 'rubygems-hosted'))
repository.createRepository(repository.createProxy('rubygems-central', 'rubygems-proxy', 'http://mirrors.aliyun.com/rubygems/'))
repository.createRepository(repository.createGroup('rubygems-public', 'rubygems-group', BlobStoreManager.DEFAULT_BLOBSTORE_NAME,  'rubygems-releases', 'rubygems-snapshot', 'rubygems-central'))
