import groovy.json.JsonSlurper
import org.sonatype.nexus.repository.config.Configuration
import org.sonatype.nexus.repository.types.GroupType
import org.sonatype.nexus.repository.types.HostedType
import org.sonatype.nexus.repository.types.ProxyType

parsed_args = new JsonSlurper().parseText(args)

def existingRepository = repository.getRepositoryManager().get(parsed_args.name)

configuration = new Configuration()

if (parsed_args.recipe == ProxyType.NAME) {
  configuration.repositoryName = parsed_args.name
  configuration.online = true
  configuration.recipeName = parsed_args.type + "-proxy"
  configuration.attributes = [
      proxy        : [
          remoteUrl     : parsed_args.remote_url,
          contentMaxAge : 1440,
          metadataMaxAge: 1440
      ],
      httpclient   : [
          connection    : [
              blocked  : false,
              autoBlock: true,
          ],
          authentication: parsed_args.remote_username == null ? null : [
              type    : 'username',
              username: parsed_args.remote_username,
              password: parsed_args.remote_password
          ]
      ],
      storage      : [
          blobStoreName              : parsed_args.blob_store,
          strictContentTypeValidation: Boolean.valueOf(parsed_args.strict_content_validation)
      ],
      negativeCache: [
          enabled   : true,
          timeToLive: 1440
      ]
  ]
} else if (parsed_args.recipe == HostedType.NAME) {
  configuration.repositoryName = parsed_args.name
  configuration.online = true
  configuration.recipeName = parsed_args.type + "-hosted"
  configuration.attributes = [
      storage: [
          blobStoreName              : parsed_args.blob_store,
          writePolicy                : parsed_args.write_policy.toUpperCase(),
          strictContentTypeValidation: Boolean.valueOf(parsed_args.strict_content_validation)
      ]
  ]
} else if (parsed_args.recipe == GroupType.NAME) {
  configuration.repositoryName = parsed_args.name
  configuration.online = true
  configuration.recipeName = parsed_args.type + "-group"
  configuration.attributes = [
      group  : [
          memberNames: parsed_args.members
      ],
      storage: [
          blobStoreName              : parsed_args.blob_store,
          strictContentTypeValidation: Boolean.valueOf(parsed_args.strict_content_validation)
      ]
  ]
}

if (parsed_args.type == "maven2") {
  configuration.attributes.maven = [
      layoutPolicy : parsed_args.layout_policy.toUpperCase(),
      versionPolicy: parsed_args.version_policy.toUpperCase()
  ]
} else if (parsed_args.type == "docker") {
  configuration.attributes.docker = [
      v1Enabled: true
  ]
  if (parsed_args.http_port) {
    configuration.attributes.docker.httpPort = Integer.valueOf(parsed_args.http_port)
  }
  if (parsed_args.https_port) {
    configuration.attributes.docker.httpsPort = Integer.valueOf(parsed_args.https_port)
  }
  if (parsed_args.recipe == ProxyType.NAME) {
    configuration.attributes.dockerProxy = [
        indexUrl : parsed_args.index_url == null ? '' : parsed_args.index_url,
        indexType: parsed_args.index_type.toUpperCase()
    ]
    configuration.attributes.httpclient.connection.useTrustStore = true
  }
}

if (existingRepository != null) {
  existingRepository.stop()
  configuration.attributes['storage']['blobStoreName'] = existingRepository.configuration.attributes['storage']['blobStoreName']
  existingRepository.update(configuration)
  existingRepository.start()
} else {
  repository.getRepositoryManager().create(configuration)
}
