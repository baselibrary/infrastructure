#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) 2016, Nandaja Varma <nandaja.varma@gmail.com>
#
#
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import json

class Kubectl:

    def __init__(self, module):
        self.module = module
        self.action = self._validated_params('action')


    def run(self):
        action_func = {
                        'create': self.kubectl_create,
                        'get': self.kubectl_get,
                        'delete': self.kubectl_delete,
                        'exec': self.kubectl_exec,
                        'stop': self.kubectl_stop,
                        'run': self.kubectl_run
                      }.get(self.action)

        try:
            return action_func()
        except:
            msg = "No method found for given action"
            self.get_output(rc=3, out=msg, err=msg)


    def kubectl_create(self):
        filename = self.module.params['filename']
        if filename:
            return "cat %s | kubectl %s -f -" % (filename, self.action)

    def kubectl_run(self):
        name = self._validated_params('name')
        image = self._validated_params('image')
        return "kubectl %s %s --image=%s" % (self.action,
                name, image)

    def kubectl_exec(self):
        pod = self._validated_params('pod')
        container = self.module.params['container']
        c_opts = '-c %s' % container if container else ''
        command = self._validated_params('command')
        if ',' in command:
            command = command.replace(',',';')
        return "kubectl %s %s %s %s" %(self.action, pod, c_opts,
                command)

    def kubectl_delete(self):
        filename = self.module.params['filename']
        if filename:
            return "cat %s | kubectl %s -f -" % (filename, self.action)
        ropts = self._validated_params('type') or ''
        label = self.module.params['label'] or ''
        if label:
            return "kubectl %s %s -l %s" % (self.action, ropts, label)
        name = self.module.params['name']
        name = ' '.join(name.split(',')) if name else '--all'
        return "kubectl %s %s %s" % (self.action, ropts, name)


    def kubectl_stop(self):
        filename = self.module.params['filename']
        if filename:
            return "cat %s | kubectl %s -f -" % (filename, self.action)
        ropts = self._validated_params('type') or ''
        uid = self.module.params['uid'] or ''
        if uid:
            return "kubectl %s %s %s" % (self.action, ropts, uid)
        label = self.module.params['label'] or ''
        if label:
            return "kubectl %s %s -l %s" % (self.action, ropts, label)
        name = self.module.params['name']
        name = ' '.join(name.split(',')) if name else '--all'
        return "kubectl %s %s %s" % (self.action, ropts, name)



    def kubectl_get(self):
        res_type = self.module.params['type']
        ropts = res_type if res_type else ''

        name = self.module.params['name']
        nopts = name if (name and ropts) else ''

        filename = self.module.params['filename']
        fopts = '-f %s' % filename if (filename and not ropts) else ''

        output = self.module.params['output']
        o_opts = '-o %s' % output if output else ''

        options = filter(None, [ropts, nopts, fopts, o_opts])
        return 'kubectl {0} {1}'.format(self.action, ' '.join(options))

    def _validated_params(self, opt):
        value = self.module.params[opt]
        if value is None:
            msg = "Please provide %s option in the playbook!" % opt
            self.module.fail_json(msg=msg)
        return value

    def get_output(self, rc=0, out=None, err=None):
        if rc:
            self.module.fail_json(msg=err, rc=rc, err=err, out=out)
        else:
            self.module.exit_json(changed=1, msg=json.dumps(out))

def main():
    module = AnsibleModule(
            argument_spec = dict(
                action          = dict(required=True, choices=["create",
                                    "stop", "run", "exec", "get", "delete"]),
                name            = dict(required=False),
                type            = dict(required=False),
                filename        = dict(required=False),
                label           = dict(required=False),
                uid             = dict(required=False),
                container       = dict(required=False),
                command         = dict(required=False),
                pod             = dict(required=False),
                output          = dict(required=False),
                image           = dict(required=False)
                ),
            supports_check_mode = True
            )


    kube = Kubectl(module)
    cmd = kube.run()
    rc, out, err = module.run_command(cmd, use_unsafe_shell=True)
    kube.get_output(rc, out, err)



from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
