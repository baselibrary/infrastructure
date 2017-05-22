#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
import gdapi
import json

def main():
  module = AnsibleModule(
    argument_spec = dict(
      url         = dict(required=False),
      access_key  = dict(required=False),
      secret_key  = dict(required=False),
      name        = dict(required=False),
      account     = dict(required=False),
      publicValue = dict(required=False),
      secretValue = dict(required=False),
      state       = dict(default='present', choices=['present', 'absent'])
    ),
    supports_check_mode = True
 )

  url         = module.params['url']
  access_key  = module.params['access_key']
  secret_key  = module.params['secret_key']
  name        = module.params['name']
  account     = module.params['account']
  publicValue = module.params['publicValue']
  secretValue = module.params['secretValue']
  state       = module.params['state']

  try:
    client = gdapi.Client(url=url, access_key=access_key, secret_key=secret_key)
    apikey = False
    for entry in client.list_api_key():
      if entry.name == name and entry.publicValue == publicValue:
          apikey = entry
          break

    changed = False
    if state == 'present':
      if apikey:
        changed = True
        response = client.update(apikey, {'accountId': account, 'name': name, 'publicValue': publicValue, 'secretValue': secretValue})
        module.exit_json(changed=True, key=module.params)
      else:
        response = client.create_api_key({'accountId': account, 'name': name, 'publicValue': publicValue, 'secretValue': secretValue})
        module.exit_json(changed=True, key=module.params)
    elif state == 'absent':
      if apikey:
        apikey.deactivate()
        apikey.remove()
        module.exit_json(changed=True)
      else:
        module.exit_json(changed=False)

    module.exit_json(changed=False)
  except gdapi.ApiError as e:
    module.fail_json(msg=str(e.error))
  except Exception as e:
    module.fail_json(msg=str(e))


if __name__ == '__main__':
  main()
