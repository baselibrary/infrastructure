#!/usr/bin/env python
# coding=utf-8

import json
import urllib
import urllib2
import logging
from copy import copy

from ansible.module_utils.basic import AnsibleModule

logger = logging.getLogger(__name__)


DOCUMENTATION = '''
---
module: dnspod
short_description: use DNSPod API to control domain
'''

EXAMPLES = '''
- action: ./library/dnspod.py -a 'token=12345,00000000000000000000000000000000 sub_domain=test base_domain=example.cn state=present record_type=A value=10.1.1.1'
- action: ./library/dnspod.py -a 'token=12345,00000000000000000000000000000000 sub_domain=test base_domain=example.cn state=absent'
'''


def dns_api(path, token, **params):
    BASE_URL = 'https://dnsapi.cn'
    http_params = copy(params)
    http_params['login_token'] = token
    http_params['record_line'] = u'默认'
    http_params['format'] = 'json'

    encoded_params = {}
    for k, v in http_params.items():
        encoded_params[k.encode('utf-8')] = v.encode('utf-8')
    req = urllib2.Request(url=BASE_URL + path,
                          data=urllib.urlencode(encoded_params))
    try:
        response = urllib2.urlopen(req)
    except Exception, e:
        logger.error(e)
        return {}
    content = response.read()
    try:
        json_content = json.loads(content)
    except Exception, e:
        logger.error(e)
        return {}
    assert json_content['status']['code'].startswith('1'), \
        'code: %s, message: %s' % (json_content.get('status', {}).get('code', 'unkown code'),
                                   json_content.get('status', {}).get('message', 'unkown error'))
    return json_content


def enabled_record_query(sub_domain, base_domain, token):
    response = dns_api(path='/Record.List',
                       token=token,
                       domain=base_domain,
                       sub_domain=sub_domain)
    if 'records' not in response:
        return []
    if len(response['records']) == 0:
        return []
    return [x for x in response['records'] if x['enabled'] == '1']


def record_present(sub_domain, base_domain, record_type, value, token):
    """
    https://www.dnspod.cn/docs/records.html#record-create
    """
    records = enabled_record_query(sub_domain, base_domain, token)
    if len(records) > 0:
        assert len(records) == 1, 'more then one records, records: %s.%s' % (
            sub_domain, base_domain)
        if records[0]['type'] == record_type and records[0]['value'] == value:
            return None  # no change
        return record_modify(sub_domain=sub_domain, base_domain=base_domain,
                             record_type=record_type, value=value, status='enable', token=token)

    response = dns_api(path='/Record.Create',
                       token=token,
                       domain=base_domain,
                       sub_domain=sub_domain,
                       record_type=record_type,
                       value=value, )
    assert 'record' in response, \
        'code: %s, message: %s' % (response.get('status', {}).get('code', 'unkown code'),
                                   response.get('status', {}).get('message', 'unkown error'))
    return response['record']


def record_disable(sub_domain, base_domain, token):
    records = enabled_record_query(sub_domain, base_domain, token)
    if len(records) == 0:
        return None  # no change
    assert len(records) == 1, 'records count is %d, domain: %s.%s' % (
        len(records), sub_domain, base_domain)
    response = dns_api(path='/Record.Modify',
                       token=token,
                       domain=base_domain,
                       record_id=records[0]['id'],
                       sub_domain=sub_domain,
                       record_type=records[0]['type'],
                       status='disable',
                       value=records[0]['value'], )
    assert 'record' in response, \
        'code: %s, message: %s' % (response.get('status', {}).get('code', 'unkown code'),
                                   response.get('status', {}).get('message', 'unkown error'))
    return response['record']


def record_modify(sub_domain, base_domain, record_type, value, status, token):
    records = enabled_record_query(sub_domain, base_domain, token)
    assert len(records) == 1, 'records count != 1, records: %s.%s' % (
        sub_domain, base_domain)
    record_id = records[0]['id']
    response = dns_api(path='/Record.Modify',
                       token=token,
                       domain=base_domain,
                       record_id=record_id,
                       sub_domain=sub_domain,
                       record_type=record_type,
                       status=status,
                       value=value, )
    assert 'record' in response, \
        'code: %s, message: %s' % (response.get('status', {}).get('code', 'unkown code'),
                                   response.get('status', {}).get('message', 'unkown error'))
    return response['record']


def main():
    module = AnsibleModule(
        argument_spec=dict(
            base_domain=dict(required=True),
            sub_domain=dict(required=True),
            record_type=dict(choices=['A', 'CNAME']),
            value=dict(),
            token=dict(required=True),
            state=dict(default='present', choices=['present', 'absent']),
        )
    )

    if module.params['state'] == 'present':
        if module.params['record_type'] is None:
            module.fail_json(msg="record_type required")
        if module.params['value'] is None:
            module.fail_json(msg="value required")

        try:
            record = record_present(sub_domain=module.params['sub_domain'],
                                    base_domain=module.params['base_domain'],
                                    record_type=module.params['record_type'],
                                    value=module.params['value'],
                                    token=module.params['token'])
            if record is None:
                module.exit_json(changed=False)
            else:
                module.exit_json(changed=True)
        except AssertionError, e:
            module.fail_json(msg=e.message)
    elif module.params['state'] == 'absent':
        try:
            record = record_disable(sub_domain=module.params['sub_domain'],
                                    base_domain=module.params['base_domain'],
                                    token=module.params['token'])
            if record is None:
                module.exit_json(changed=False)
            else:
                module.exit_json(changed=True)
        except AssertionError, e:
            module.fail_json(msg=e.message)


if __name__ == '__main__':
    main()
