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
import networkx as nx
import yaml
from time import sleep
from yaml import composer

from taskflow import task
from taskflow import engines
from taskflow.patterns import graph_flow


class BaseServiceTask(task.Task):
    def __init__(self, provides=None, requires=None,
                 execute=None, name=None, config=None):
        super(BaseServiceTask, self).__init__(provides=provides,
                                              requires=requires,
                                              name=name)
        self.config = config

    def revert(self, *args, **kwargs):
        print ("Task '%s' is REVERTING" % self.name)

    #TODO (nmakhotkin) here should be a really action
    def do_action(self, *args, **kwargs):
        pass

    def execute(self, *args, **kwargs):
        return self.do_action(args, kwargs)


class ServiceTask(BaseServiceTask):
    def do_action(self, *args, **kwargs):
        action = self.config["actions"][self.name]
        transport_name = action.get("transport", None)
        print("Action executing: " + self.name + ",")
        print("Doing " + str(action))
        if transport_name:
            transport = self.config["transports"][transport_name]
            print("transport: " + str(transport))
            print("")
        sleep(0.5)


def get_task(task_name, task_data, config):
    return ServiceTask(
        provides=task_name,
        requires=task_data.get("requires", []),
        name=task_name,
        config=config
    )


def get_stream(file_name):
    return open(file_name).read()


def load_flow(cfg_stream):
    try:
        config = yaml.load(cfg_stream)
    except composer.ComposerError:
        config = json.loads(cfg_stream)
    except ValueError:
        raise RuntimeError("Config could not be parsed.")
    tasks = config["tasks"]
    name = tasks.items()[-1][0]
    flow = graph_flow.Flow(name)
    for name, data in tasks.items():
        flow.add(get_task(name, data, config))
    return flow


def get_by_name(graph, name):
    for node in graph:
        if node.name == name:
            return node
    return None


def get_root(graph):
    for node in graph:
        if len(graph.predecessors(node)) == 0:
            return node


if __name__ == "__main__":
    flow = load_flow(get_stream("concepts/use_case_example.yaml"))
    graph = nx.DiGraph(flow._graph.copy())
    ex_cfg = json.load(open("concepts/execute_config.json"))
    all_paths = nx.all_simple_paths(graph,
                                    get_root(graph),
                                    get_by_name(graph,
                                                ex_cfg["executeTask"]))
    nodes_set = set([node for path in all_paths for node in path])
    sub_graph = graph.subgraph(nodes_set)
    our_flow = graph_flow.Flow(name=flow.name)
    our_flow._swap(sub_graph)
    engines.run(our_flow, engine_conf="parallel")
