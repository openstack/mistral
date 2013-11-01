# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from time import sleep

from taskflow import task
from taskflow import engines
from taskflow.patterns import graph_flow


class BaseServiceTask(task.Task):
    def __init__(self, provides=None, requires=None,
                 execute=None, name=None):
        super(BaseServiceTask, self).__init__(provides=provides,
                                              requires=requires,
                                              name=name)
        self.func = execute

    def revert(self, *args, **kwargs):
        print ("Task '%s' is REVERTING" % self.name)

    def execute(self, *args, **kwargs):
        print (self.name)
        sleep(2)
        return self.name


def get_task(task_config):
    return BaseServiceTask(
        provides=task_config.get("provides", []),
        requires=task_config.get("requires", []),
        name=task_config["name"]
    )


def load_flow(config_path):
    config = json.loads(open(config_path).read())
    tasks = config["config"]["tasks"]
    flow = graph_flow.Flow(config["flowName"])
    for task in tasks:
        flow.add(get_task(task))
    return flow


if __name__ == "__main__":
    flow = load_flow("use_case_example.json")
    engines.run(flow, engine_conf="parallel")
