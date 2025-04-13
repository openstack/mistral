# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

class WorkflowGenerator(object):

    def _generate_task(self, name, subwf=None, action=None, publish=None,
                       join=None, on_success=None, timeout=None,
                       with_items=None, concurrency=None):
        task_body = {}

        if subwf:
            task_body["workflow"] = subwf
        elif action:
            task_body["action"] = action

        if publish:
            task_body["publish"] = publish

        if join:
            task_body["join"] = join

        if on_success:
            task_body["on-success"] = on_success

        if timeout:
            task_body["timeout"] = timeout

        if with_items:
            task_body["with-items"] = f"v in <% range({with_items}) %>"
            task_body["concurrency"] = 1 if not concurrency else int(concurrency)

        task = {
            name: task_body
        }

        return task

    def _generate_wf_with_joins(self, wf_name, branch_count,
                                         branch_length, publish=None):
        branch_count, branch_length = int(branch_count), int(branch_length)

        wf_def = {
            "version": "2.0"
        }

        wf_body = {
            "tasks": {}
        }

        for pos in range(branch_length):
            for branch in range(branch_count):
                task_name = f"task_{branch}_{pos}"
                join = "all" if pos > 0 else None
                on_success = [f"task_{br}_{pos + 1}"
                              for br in range(branch_count)] \
                    if pos < branch_length - 1 \
                    else None
                wf_body["tasks"].update(
                    self._generate_task(
                        name=task_name,
                        action="std.noop",
                        publish=publish,
                        join=join,
                        on_success=on_success
                    )
                )

        wf_def[wf_name] = wf_body

        return wf_def

    def _generate_wf_with_nested_wf(self, task_count, depth):
        task_count, depth = int(task_count), int(depth)

        wfs_def = {
            "version": "2.0"
        }

        for i in range(depth):
            if i == 0:
                wf_name = f"wf_with_nested_wfs_{task_count}_{depth}"
            else:
                wf_name = f"wf_with_nested_wfs_{task_count}_{depth}_{i}"

            wf_body = {
                "tasks": {}
            }

            for j in range(task_count):
                task_name = f"task_{j}"
                if i == (depth - 1):
                    task = self._generate_task(task_name, action="std.noop")
                else:
                    subwf_name = f"wf_with_nested_wfs_" \
                        f"{task_count}_{depth}_{i + 1}"
                    task = self._generate_task(task_name, subwf=subwf_name)

                wf_body["tasks"].update(task)

            wfs_def[wf_name] = wf_body

        return wfs_def

    def _generate_wf_with_items(self, with_items_count, concurrency):
        wfs_def = {
            "version": "2.0"
        }

        wf_name = f"wf_with_items_{with_items_count}_{concurrency}"

        wf_body = {
            "tasks": {}
        }

        task = self._generate_task(
            name="with_items_task",
            action="std.sleep seconds=1",
            with_items=with_items_count,
            concurrency=concurrency
        )

        wf_body["tasks"].update(task)

        wfs_def[wf_name] = wf_body

        return wfs_def

    def generate_parallel_wf_with_joins(self,
                                        branch_count,
                                        branch_length):

        wf_name = f"parallel_wf_with_joins_{branch_count}_{branch_length}"
        wf_def = self._generate_wf_with_joins(wf_name,
                                              branch_count,
                                              branch_length)

        return wf_name, wf_def

    def generate_wf_with_context_merge(self,
                                       branch_count,
                                       branch_length,
                                       data_count,
                                       data_length):

        wf_name = f"wf_with_context_merge_" \
                  f"{data_count}_{data_length}"

        wf_def = self._generate_wf_with_joins(
            wf_name,
            branch_count,
            branch_length,
            publish={
                "context": f"<% generate_random_data"
                           f"({data_count}, {data_length}) %>"
            }
        )

        return wf_name, wf_def

    def generate_wf_with_nested_wfs(self,
                                    task_count,
                                    depth):
        root_wf_name = f"wf_with_nested_wfs_{task_count}_{depth}"

        wf_def = self._generate_wf_with_nested_wf(task_count, depth)

        return root_wf_name, wf_def

    def generate_wf_with_items(self, with_items_count, concurrency):
        root_wf_name = f"wf_with_items_{with_items_count}_{concurrency}"

        wf_def = self._generate_wf_with_items(with_items_count, concurrency)

        return root_wf_name, wf_def

if __name__ == '__main__':
    generator = WorkflowGenerator()

    import requests

    mistral_url = "http://localhost:8989/v2"

    # wf = generator.generate_parallel_wf_with_joins(
    #     branch_count=100,
    #     branch_length=10
    # )

    wf_name, wf = generator.generate_wf_with_items(10, 2)

    print(wf)

    print(len(str(wf)))

    res = requests.post(mistral_url + "/workflows", json=wf)
    res.raise_for_status()
