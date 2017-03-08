#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
import requests
from requests.exceptions import HTTPError

DOCUMENTATION = """
---
module: marathon
short_description: manage marathon apps
description:
  - Create, update or delete an app via the Marathon API.
options:
  args:
    description:
      - List of arguments passed to a task
    required: false
    default: null
    aliases: []
  backoff_seconds:
    description:
      - Time Marathon waits until it tries to run a previously failing task.
    required: false
    default: 1
    aliases: []
  cpus:
    description:
      - Set number of CPUs to allocate for one container
    required: False
    default: 1.0
    aliases: []
  command:
    description:
      - Set the command to execute in a container.
    required: False
    default: null
    aliases: []
  constraints:
    description:
      - Control where apps run.
    required: false
    default: null
    aliases: []
  container:
    description:
      - Options of a container.
    required: False
    default: dict
    aliases: []
  env:
    description:
      - Key/value pairs passed to a container as environment variables.
    required: False
    default: dict
    aliases: []
  health_checks:
    description:
      - A list of health checks that Marathon should execute
    required: False
    default: list
    aliases: []
  host:
    description:
      - Set the URL to a Marathon host.
    required: False
    default: http://localhost:8080
    aliases: []
  labels:
    description:
      - Add labels to the application.
    required: False
    default: dict
    aliases: []
  instances:
    description:
      - Set the number of instances to spawn.
    required: False
    default: 1
    aliases: []
  max_launch_delay_seconds:
    description:
      - Time until a deployment is considered failed.
    required: False
    default: 3600
    aliases: []
  memory:
    description:
      - Set how much memory to assign to an instance.
    required: False
    default: 256.0
    aliases: []
  name:
    description:
      - Set the name of the app.
    required: True
    default: null
    aliases: []
  ports:
    description:
      - List of ports passed to a task
    required: false
    default: null
    aliases: []
  state:
    description:
      - Indicate desired state of the target.
    required: False
    default: present
    choices: ['present', 'absent']
  wait:
    description:
      - Wait until all new tasks are in 'running' state.
    required: False
    default: yes
    choices: ['yes', 'no']
  wait_timeout:
    description:
      - Time to wait for a deployment to finish.
    required: False
    default: 300
"""

EXAMPLES = """
# Run a command in a container (note that the execution is delegated to localhost):
- hosts: localhost
  connection: local
  gather_facts: no
  sudo: no
  tasks:
    - marathon:
        state: present
        name: /simple_app
        host: http://marathon.example.com:8080
        memory: 16.0
        instances: 1
        command: env && sleep 300
      register: marathon
    - debug: var=marathon
# Run the Docker Registry inside a docker container and expose its HTTP port:
- hosts: localhost
  connection: local
  gather_facts: no
  sudo: no
  tasks:
    - marathon:
        state: present
        name: /docker-registry
        host: http://marathon.example.com:8080
        memory: 128.0
        instances: 1
        container:
          type: DOCKER
          docker:
            image: registry:0.8.1
            network: BRIDGE
            portMappings:
              - { containerPort: 5000, hostPort: 0, protocol: "tcp" }
        env:
          SETTINGS_FLAVOR: local
          SEARCH_BACKEND: sqlalchemy
"""


class TimeoutError(Exception):
    pass


class UnknownAppError(Exception):
    pass


class Marathon(object):
    def __init__(self, module):
        self._module = module

    def create(self):
        url = "{0}/v2/apps".format(self._module.params["host"])

        rep = requests.post(url, data=json.dumps(self._updated_data()), headers={"Content-Type": "application/json"})
        rep.raise_for_status()

        data = rep.json()

        self._check_deployment(data["deployments"][0]["id"])

    def delete(self):
        rep = requests.delete(self._url())
        rep.raise_for_status()

    def exists(self):
        try:
            self._retrieve_app()
        except UnknownAppError:
            return False

        return True

    def gather_facts(self):
        app = self._retrieve_app()

        namespaces = app["id"].split("/")
        # First item in the list empty due to "id" starting with "/"
        del namespaces[0]

        app["namespaces"] = namespaces

        return app

    def needs_update(self, app):
        app["uris"].sort()
        module_uris = self._module.params["uris"] or []
        module_uris.sort()

        if (self._args_changed(app, self._module)
                or app["backoffFactor"] != self._module.params["backoff_factor"]
                or app["backoffSeconds"] != self._module.params["backoff_seconds"]
                or app["cmd"] != self._sanitize_command()
                or app["cpus"] != self._module.params["cpus"]
                or app["env"] != self._sanitize_env()
                or app["healthChecks"] != (self._module.params["health_checks"] or [])
                or app["instances"] != self._module.params["instances"]
                or app["labels"] != (self._module.params["labels"] or {})
                or app["maxLaunchDelaySeconds"] != self._module.params["max_launch_delay_seconds"]
                or app["mem"] != self._module.params["memory"]
                or app["uris"] != module_uris):
            return True

        new_container = self._container_from_module()
        if app["container"]["type"] != new_container["type"]:
            return True

        if self._docker_container_changed(app["container"]["docker"],
                                          new_container["docker"]):
            return True

        if app["container"]["volumes"] != new_container["volumes"]:
            return True

        if self._module.params["constraints"] is None:
            module_constraints = []
        else:
            module_constraints = self._module.params["constraints"]
        if module_constraints != app["constraints"]:
            return True

        if self._module.params["ports"] is None:
            module_ports = []
        else:
            module_ports = self._module.params["ports"]
        if module_ports != app["ports"]:
            return True

        return False

    def sync(self):
        if self._module.params["state"] == "present":
            try:
                app = self._retrieve_app()
                if self.needs_update(app):
                    self.update(app)
                    self._module.exit_json(app=self.gather_facts(), changed=True)
                else:
                    self._module.exit_json(app=self.gather_facts(),changed=False)
            except HTTPError:
                self.create()
                self._module.exit_json(app=self.gather_facts(), changed=True)

        if self._module.params["state"] == "absent":
            try:
                self._retrieve_app()
                self.delete()
                self._module.exit_json(changed=True)
            except HTTPError:
                self._module.exit_json(changed=False)

    def update(self, app):
        previous_version = app["version"]

        rep = requests.put(self._url(), data=json.dumps(self._updated_data()), headers={"Content-Type": "application/json"})
        rep.raise_for_status()

        data = rep.json()

        self._check_deployment(data["deploymentId"])

    def _check_deployment(self, deployment_id):
        if self._module.params["wait"] is False:
            return

        timeout = int(time.time()) + self._module.params["wait_timeout"]

        while int(time.time()) < timeout:
            time.sleep(5)
            url = "{0}/v2/deployments".format(self._module.params["host"])
            rep = requests.get(url)
            rep.raise_for_status()

            data = rep.json()

            found = False

            for _, deployment in enumerate(data):
                if deployment["id"] == deployment_id:
                    found = True

            if found is False:
                return

        raise TimeoutError("Marathon deployment timed out")

    def _container_from_module(self):
        container = {}

        if "container" not in self._module.params:
            return container

        if "docker" in self._module.params["container"]:
            container["docker"] = self._module.params["container"]["docker"]

        if "type" in self._module.params["container"]:
            container["type"] = self._module.params["container"]["type"]

        if "volumes" in self._module.params["container"]:
            container["volumes"] = self._module.params["container"]["volumes"]
        else:
            container["volumes"] = []

        if "portMappings" in container["docker"]:
            # Set service ports to 0 for easier comparison
            for key, pm in enumerate(container["docker"]["portMappings"]):
                if "servicePort" not in pm:
                    container["docker"]["portMappings"][key]["servicePort"] = 0

        return container

    def _args_changed(self, app, module):
        app_args = app["args"] or []
        module_args = module.params["args"] or []

        app_args.sort()
        module_args.sort()

        return app_args != module_args

    def _docker_container_changed(self, app, module):
        if app["image"] != module["image"]:
            return True

        if ("network" not in app and "network" in module) or ("network" in app and "network" not in module):
            return True

        if "network" in app and "network" in module and app["network"] != module["network"]:
            return True

        app_port_mappings = app["portMappings"] if "portMappings" in app else []
        module_port_mappings = module["portMappings"] if "portMappings" in module else []

        if len(app_port_mappings) != len(module_port_mappings):
            return True

        found = 0

        for pm_module in module["portMappings"]:
            for pm_app in app["portMappings"]:
                service_port_equal = True

                if (pm_module["servicePort"] == 0
                    and (pm_app["servicePort"] < self._module.params["local_port_min"]
                         or pm_app["servicePort"] > self._module.params["local_port_max"])):
                    service_port_equal = False

                if (pm_module["servicePort"] != 0
                        and pm_module["servicePort"] != pm_app["servicePort"]):
                    service_port_equal = False

                if (service_port_equal
                        and pm_module["containerPort"] == pm_app["containerPort"]
                        and pm_module["hostPort"] == pm_app["hostPort"]
                        and pm_module["protocol"] == pm_app["protocol"]):
                    found += 1

        if found != len(module["portMappings"]):
            return True

        return False

    def _id(self):
        if self._module.params["name"][0] == "/":
            return self._module.params["name"]

        return "/" + self._module.params["name"]

    def _retrieve_app(self):
        req = requests.get(self._url())

        req.raise_for_status()

        data = req.json()

        return data["app"]

    def _sanitize_command(self):
        if self._module.params["command"]:
            return self._module.params["command"]
        return None

    def _sanitize_env(self):
        env = self._module.params["env"]

        for env_key in env:
            if isinstance(env[env_key], str) is False:
                env[env_key] = str(env[env_key])

        return env

    def _updated_data(self):
        return {
            "args": self._module.params["args"],
            "ports": self._module.params["ports"],
            "backoffFactor": self._module.params["backoff_factor"],
            "backoffSeconds": self._module.params["backoff_seconds"],
            "cmd": self._sanitize_command(),
            "constraints": self._module.params["constraints"],
            "container": self._container_from_module(),
            "cpus": self._module.params["cpus"],
            "id": self._id(),
            "env": self._sanitize_env(),
            "healthChecks": self._module.params["health_checks"],
            "labels": self._module.params["labels"],
            "instances": self._module.params["instances"],
            "maxLaunchDelaySeconds": self._module.params["max_launch_delay_seconds"],
            "mem": self._module.params["memory"],
            "uris": self._module.params["uris"] or []
        }

    def _url(self):
        url = "{0}/v2/apps".format(self._module.params["host"])

        if self._module.params["name"][0] != "/":
            url += "/"

        url += self._module.params["name"]

        return url


def main():
    module = AnsibleModule(
        argument_spec=dict(
            args=dict(default=None, type="list"),
            backoff_factor=dict(default=1.15, type="float"),
            backoff_seconds=dict(default=1, type="int"),
            cpus=dict(default=1.0, type="float"),
            command=dict(default=None, type="str"),
            constraints=dict(default=None, type="list"),
            container=dict(default=None, type="dict"),
            env=dict(default=dict(), type="dict"),
            health_checks=dict(default=list(), type="list"),
            host=dict(default="http://localhost:8080", type="str"),
            instances=dict(default=1, type="int"),
            labels=dict(default=None, type="dict"),
            local_port_max=dict(default=20000, type="int"),
            local_port_min=dict(default=10000, type="int"),
            max_launch_delay_seconds=dict(default=3600, type="int"),
            memory=dict(default=256.0, type="float"),
            name=dict(required=True, type="str"),
            ports=dict(default=None, type="list"),
            state=dict(default="present", choices=["absent", "present"], type="str"),
            uris=dict(default=None, type="list"),
            wait=dict(default="yes", choices=BOOLEANS, type="bool"),
            wait_timeout=dict(default=300, type="int")
        ),
        mutually_exclusive=(["args", "cmd"],)
    )

    try:
        marathon = Marathon(module=module)

        marathon.sync()
    except HTTPError, e:
        raw_message = e.response.json()
        if "message" in raw_message:
            module.fail_json(msg=raw_message["message"])
        else:
            module.fail_json(msg=str(e))
    except TimeoutError, e:
        module.fail_json(msg=str(e))

from ansible.module_utils.basic import *
main()