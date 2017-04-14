#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
import gdapi
import json
from time import sleep

DOCUMENTATION = '''
---
module: rancher
short_description: Rancher module to configure stacks / environments / catalogs
description:
    - With this module you can either update your catalogs or environments and define stacks on an environment
version_added: "1.0"
author: "Remi Cattiau, @loopingz"
notes:
    - Other things consumers of your module should know 
    - Additional setting requirements
requirements:
    - gdapi
options:
    url:
        description:
            - Rancher URL
        required: true
    access_key:
        description:
            - Rancher Account Access Key
        required: true
    secret_key:
        description:
            - Rancher Account Secret Key
        required: true
    catalogs:
        description:
            - List of catalogs you want to install: list of map(url,name,[branch])
        required: false
    clean_catalogs:
        description:
            - Remove any catalogs that are not specified ( default=False )
        required: false
    environments:
        description:
            - List of environments you want to have: list of map(name,stacks)
            - stacks are list of map(name,catalog_entry|(docker_compose,rancher_compose),[answers])
            - answers are a list of map(name,value)
            - catalog_entry is format CatalogName:TemplateName[:Version]
        required: false
    clean_envs:
        description:
            - Remove any envs that are not specified ( default=False )
        required: false
    clean_stacks:
        description:
            - Remove any stacks that are not specified ( default=False )
        required: false
'''


class ProjectAutomationClient(gdapi.Client):

    def __init__(self, url, root_client, project_id, *args, **kwargs):
        self._project_id = project_id
        self._root_client = root_client
        self._init = False
        if url[-1] != '/':
            url += '/'
        url += 'v2-beta/projects/' + project_id
        super(ProjectAutomationClient, self).__init__(url=url, *args, **kwargs)

    def _load_schemas(self, *args, **kwargs):
        if not self._init:
            return
        super(ProjectAutomationClient, self)._load_schemas(*args, **kwargs)

    def __enter__(self):
        # Creating key for environment
        key_name = 'io-deploy-automation'
        self._key = self._root_client.create_api_key({'accountId': self._project_id, 'name': key_name})
        self._access_key = self._key.publicValue
        self._secret_key = self._key.secretValue
        self._auth = (self._access_key, self._secret_key)
        self._init = True
        while True:
            try:
                self._load_schemas()
            except gdapi.ApiError:
                # Wait until key is active
                sleep(1)
                continue
            break
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Desactivate environment API key
        self._key = self._root_client._post(self._key.links.self + "?action=deactivate")
        # Remove environment API key
        while True:
            try:
                self._root_client.delete(self._key)
            except gdapi.ApiError:
                # Wait until key is deactived
                sleep(1)
                continue
            break


class RancherAnsibleModule(AnsibleModule):
    def __init__(self, *args, **kwargs):
        self._output = []
        self._facts = dict()
        self._account_client = None
        self._catalog_client = None
        super(RancherAnsibleModule, self).__init__(*args, **kwargs)

    def list_catalog(self, name):
        return self._catalog_client.list_template(catalogId=name).data

    def get_catalog_template(self, catalog, template):
        for entry in self.list_catalog(catalog):
            path = entry.path.split('/')
            if path[1] == template:
                return entry
        return None

    def init_stack(self, stack):
        stack['definition'] = dict()
        stack['definition']['name'] = stack['name']
        stack['definition']['type'] = 'stack'

        # Init the default values
        if 'startOnCreate' in stack:
            stack['definition']['startOnCreate'] = stack['startOnCreate']
        else:
            stack['definition']['startOnCreate'] = True
        stack['definition']['environment'] = dict()
        # Inject any additional environment
        if 'answers' in stack:
            for answer in stack['answers']:
                stack['definition']['environment'][answer['name']] = answer['value']

        if 'catalog_entry' in stack:
            # Load catalog
            infos = stack['catalog_entry'].split(':')
            if len(infos) < 2 or len(infos) > 3:
                raise Exception('Catalog entry format is CatalogName:TemplateName[:Version] \'%s\' is invalid' %\
                                    (stack['catalog_entry'],))
            catalog_template = self.get_catalog_template(infos[0], infos[1])
            if catalog_template is None:
                raise Exception('Catalog entry not found: %s' % (stack['catalog_entry'],))
            if len(infos) == 2:
                infos.append(catalog_template.defaultVersion)
            url = catalog_template.versionLinks[infos[2]]
            template = self._catalog_client.by_id_template(url[url.rindex('/') + 1:])
            stack['definition']['rancherCompose'] = template.files['rancher-compose.yml']
            stack['definition']['dockerCompose'] = template.files['docker-compose.yml']
        elif not ('docker_compose' in stack and 'rancher_compose' in stack):
            # Check arguments failed
            raise Exception('Stack need to have either catalog_entry or docker_compose and rancher_compose')
        else:
            # Use compose information
            stack['definition']['rancherCompose'] = stack['rancher_compose']
            stack['definition']['dockerCompose'] = stack['docker_compose']

    def equals_stack(self, expected_stack, stack):
        if not (expected_stack['definition']['dockerCompose'] == stack.dockerCompose and \
                expected_stack['definition']['rancherCompose'] == stack.rancherCompose):
            return False
        for key, value in expected_stack['definition']['environment'].items():
            if stack.environment[key] != value:
                return False
        return True

    def check_environment(self, env, expected_env):
        with ProjectAutomationClient(self.params['url'], self._account_client, env.id) as client:
            stacks = client.list_stack().data
            adds = []
            updates = []
            names = []
            result = False
            for expected_stack in expected_env['stacks']:
                names.append(expected_stack['name'])
                self.init_stack(expected_stack)
                found = False
                for stack in stacks:
                    if stack.name == expected_stack['name']:
                        found = True
                        # Check modification
                        if not self.equals_stack(expected_stack, stack):
                            expected_stack['current'] = stack.links.self
                            updates.append(expected_stack)
                        break
                if found:
                    continue
                adds.append(expected_stack)
            removes = []
            if self.params['clean_stacks']:
                for stack in stacks:
                    if not stack.name in names:
                        removes.append(stack)
            '''
            for item in catalog:
                if item.name in launch:
                    print "Launching stack " + item.name
                    launch_stack(item, catalog_client, client, launch[item.name], stacks)
            print client.list_registration_token().data[0].token
            '''
            result |= (len(removes) + len(adds) + len(updates)) != 0
            # Push all registration_token
            # client.list_registration_token().data[0].token
            # Check mode don't actually update stuffs
            if self.check_mode:
                return result
            # Launch update process
            for stack in updates:
                client._post(stack['current'] + "?action=upgrade", stack['definition'])
            for stack in updates:
                current = client._get(stack['current'])
                while current.state == 'upgrading':
                    sleep(1)
                    current = client.reload(current)
                if current.state == 'upgraded':
                    client._post(stack['current'] + "?action=finishupgrade")
                else:
                    raise Exception("Cant update the stack " + stack['current'])

            # Adding stack
            for stack in adds:
                client.create_stack(stack['definition'])
        return result

    def get_environment_token(self, env, iter=0):
        tokens = self._account_client._get(env.links['registrationTokens']).data

        if len(tokens) > 0:
            return tokens[0].token
        else:
            if (iter > 3):
                raise Exception('Cannot create environment token')
            self._account_client._post(env.links['registrationTokens'][:-1])
            sleep(1)
            return self.get_environment_token(env, iter=iter+1)

    def check_environments(self, expected_envs):
        # Get environments
        envs = self._account_client.list_project().data
        adds = []
        names = []
        result = False
        for expected_env in expected_envs:
            names.append(expected_env['name'])
            found = False
            for env in envs:
                if env.name == expected_env['name']:
                    found = True
                    # Check environment
                    result |= self.check_environment(env, expected_env)
                    break
            if found:
                continue
            adds.append(expected_env)
        removes = []
        self._facts["envs"] = dict()
        # If in clean mode remove the unwanted environments
        for env in envs:
            if not env.name in names:
                if self.params['clean_envs']:
                    removes.append(env)
                    continue
            self._facts["envs"][env.name] = dict()
            self._facts["envs"][env.name]["token"] = self.get_environment_token(env)
        result |= (len(removes) + len(adds)) != 0
        # Check mode don't actually update stuffs
        if self.check_mode:
            return result
        # Create missing environment
        for env in adds:
            created_env = self._account_client.create_project({'name': env['name']})
            # Add the stack now
            self.check_environment(created_env, env)
            self._facts["envs"][created_env.name] = dict()
            self._facts["envs"][created_env.name]["token"] = self.get_environment_token(created_env)
        # Remove additional environment
        for env in removes:
            self._account_client.delete(env)
        return result

    def check_catalogs(self, expected_catalogs):
        # Get catalog settings
        catalog_url_id = '1as17'
        setting = self._account_client.by_id_setting(catalog_url_id)
        catalogs = json.loads(setting.value)['catalogs']
        urls = []
        adds = []
        updates = []
        # Verify if expected catalogs already exists or need updates
        for expected_catalog in expected_catalogs:
            urls.append(expected_catalog['url'])
            # By default use master branch
            if not 'branch' in expected_catalog:
                expected_catalog['branch'] = 'master'
            found = False
            for key, catalog in catalogs.iteritems():
                if expected_catalog['url'] == catalog['url'] or expected_catalog['name'] == key:
                    found = True
                    if expected_catalog['url'] == catalog['url'] and expected_catalog['name'] == key\
                            and expected_catalog['branch'] == catalog['branch']:
                        break
                    updates.append(expected_catalog)
                    break
            if found:
                continue
            adds.append(expected_catalog)

        removes = []
        # If in clean mode remove the unwanted catalogs
        if self.params['clean_catalogs']:
            for key, catalog in catalogs.iteritems():
                if not catalog[u'url'] in urls:
                    removes.append(catalog)
            # It will reinit the catalogs
            catalogs = dict()
        result = (len(removes) + len(adds) + len(updates)) != 0
        self._catalogs = catalogs
        # Check mode don't actually update stuffs
        if self.check_mode:
            return result
        # Update the settings according to the catalog requested
        for catalog in adds:
            catalogs[catalog['name']] = {'url': catalog['url'], 'branch': catalog['branch']}
        for catalog in updates:
            if catalog['name'] in catalogs:
                catalogs[catalog['name']]['url'] = catalog['url']
                catalogs[catalog['name']]['branch'] = catalog['branch']
            else:
                catalogs[catalog['name']] = {'url': catalog['url'], 'branch': catalog['branch']}
        setting['value'] = json.dumps({'catalogs': catalogs})
        self._account_client.update_by_id_setting(catalog_url_id, setting)
        self._catalogs = catalogs
        return result

    def log(self, msg, *args, **kwargs):
        self._output.append(msg % kwargs)
        super(RancherAnsibleModule, self).log(msg, *args, **kwargs)

    def process(self):
        try:
            changed = False
            self._account_client = gdapi.Client(url=self.params['url'] + 'v2-beta/',
                                                    access_key=self.params['access_key'],
                                                    secret_key=self.params['secret_key'])
            self._catalog_client = gdapi.Client(url=self.params['url'] + 'v1-catalog/',
                                                access_key=self.params['access_key'],
                                                secret_key=self.params['secret_key'])
            if 'catalogs' in self.params:
                changed |= self.check_catalogs(self.params['catalogs'])
            if 'environments' in self.params:
                changed |= self.check_environments(self.params['environments'])
            self.exit_json(changed=changed, ansible_facts={'rancher': self._facts},
                                output=self._output, catalogs=self._catalogs)
        except Exception as e:
            self.fail_json(msg=e.message)


def main():
    RancherAnsibleModule(
        argument_spec = dict(
            url      = dict(required=True),
            access_key=dict(required=True),
            secret_key=dict(required=True),
            clean_envs=dict(default=False,type='bool'),
            clean_catalogs=dict(default=False, type='bool'),
            clean_stacks=dict(default=False, type='bool'),
            catalogs = dict(type='list'),
            environments = dict(type='list')
        ),
        supports_check_mode=True
    ).process()

if __name__ == '__main__':
    main()