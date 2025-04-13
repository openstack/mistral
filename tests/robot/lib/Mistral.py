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

import functools
import json
import time
import uuid
from distutils import util
from typing import Dict
from urllib import parse

import requests
from robot import utils
from robot.api import logger
from robot.utils import asserts, dotdict

import idp
from utils import timeout

SKIPPED_WORKFLOWS = ['std.create_instance', 'std.delete_instance', 'main_wf']

NUMBER_OF_PARENT_TASKS = 44

NUMBER_OF_CHILD_TASKS = 2


def process_workflow_file(workflow_name):
    return "workflows/{}.yaml".format(workflow_name)


def process_workbook_file(workflow_name):
    return "workbook/{}.yaml".format(workflow_name)


def process_json_resource_file(file_name):
    return "resources/{}.json".format(file_name)


def extract_api_fault_string(json_dict):
    return json_dict['faultstring']


def assert_response(res, status_code=200):
    if isinstance(status_code, list):
        asserts.assert_true(res.status_code in status_code, res.text)
    else:
        asserts.assert_equal(status_code, res.status_code, res.text)


def retry(func, *args, **kwargs):
    for _ in range(24):
        try:
            return func(*args, **kwargs)
        except BaseException as e:
            logger.error(str(e))

        time.sleep(5)

    raise Exception(f"Timeout for func {func.__name__} is up")


class ExecutionException(Exception):

    def __init__(self, message, wf_ex: Dict[str, str] = {}, task_ex: Dict[str, str] = {}):
        super().__init__(f'Workflow execution: [id={wf_ex.get("id")}, name={wf_ex.get("workflow_name")}]. '
                         f'Task execution: [id={task_ex.get("id")}, name={task_ex.get("name")}]. {message}')


def error_handler(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        self = args[0]
        try:
            self._tenant = kwargs.get('tenant')

            if self._tenant:
                del kwargs['tenant']
            elif self._auth_enable:
                self._tenant = self._main_tenant

            return f(*args, **kwargs)
        finally:
            self._tenant = None

    return wrapper


class Mistral(object):

    def __init__(self, mistral_url='1', auth_enable='f', auth_type='mitreid',
                 client_register_token=None, idp_server=None,
                 tenant=None, idp_user=None, idp_password=None,
                 multitenancy_enabled='False', idp_client_id=None,
                 idp_client_secret=None, workflow_namespace=None):
        self._mistral_url = mistral_url
        self._auth_enable = util.strtobool(auth_enable.lower())
        self._auth_type = auth_type
        self._main_tenant = tenant
        self._idp_user = idp_user
        self._idp_password = idp_password
        self._multitenancy_enabled = util.strtobool(multitenancy_enabled.lower())
        self._workflow_namespace = workflow_namespace

        self._ex_id = None
        self._ex_ids = set()
        self._workflows = []
        self._workbooks = []
        self._tasks = None
        self._tenant = None
        self._tokens = {}

        if self._auth_enable:
            if self._auth_type == 'mitreid':
                self._idp = idp.MitreidLibrary(idp_server,
                                               client_register_token,
                                               idp_client_id=idp_client_id,
                                               idp_client_secret=idp_client_secret)
            elif self._auth_type == 'keycloak-oidc':
                self._idp = idp.KeycloakLibrary(idp_server,
                                                client_register_token,
                                                idp_client_id=idp_client_id,
                                                idp_client_secret=idp_client_secret)

        logger.info(f'Mistral parameters: {self.__dict__}')

    def get_not_exist_workflow(self):
        res = requests.request('GET', self._mistral_url + '/workflows/123', timeout=5)

        return str(res.status_code)

    def get_token(self):
        if not self._auth_enable:
            return ""

        tenant = self._tenant if self._tenant else self._main_tenant

        token = self._tokens.get(tenant)

        if not token:
            if self._multitenancy_enabled:
                token = self._idp.get_multitenancy_token(
                    tenant, self._idp_user, self._idp_password)
            else:
                token = self._idp.get_token()

            logger.debug(f'Get token {token} for {tenant}')

            self._tokens[tenant] = token

        return token

    @error_handler
    def create_workflow(self, name: str):
        with open(process_workflow_file(name), 'r') as f:
            workflow_str = f.read()

        # workbook doesn't support namespaces
        if '.' in name:
            url = f'{self._mistral_url}/workflows'
        else:
            url = f'{self._mistral_url}/workflows?namespace={self._workflow_namespace}'

        res = self._security_request('POST', url, data=workflow_str)
        status_code = res.status_code

        if status_code not in (409, 423):
            assert_response(res, 201)

            self._workflows.append(name)

        return status_code

    def create_workflow_by_json_definition(self, definition):
        url = f'{self._mistral_url}/workflows?namespace={self._workflow_namespace}'
        res = self._security_request('POST', url, json=definition)
        status_code = res.status_code

        if status_code not in (409, 423):
            assert_response(res, 201)
        wf_names = self.extract_workflow_names(definition)
        for name in wf_names:
            self._workflows.append(name)
        return status_code
    

    def extract_workflow_names(self, data):
        workflow_names = []

        def extract_names(sub_data):
            for key, value in sub_data.items():
                if isinstance(value, dict):
                    if 'tasks' in value:
                        workflow_names.append(key)
                    extract_names(value)
        
        extract_names(data)
        return workflow_names

    @error_handler
    def get_workflow_http_status(self, name):
        res = self._security_request('GET',
                                     self._mistral_url +
                                     f"/workflows/{name}?namespace={self._workflow_namespace}")

        return res.status_code

    @error_handler
    def delete_workflow(self, name):
        res = self._security_request('DELETE',
                                     self._mistral_url +
                                     f"/workflows/{name}?namespace={self._workflow_namespace}")
        assert_response(res, [404, 204])

        try:
            self._workflows.remove(name)
        except ValueError as e:
            logger.debug(e)

    @error_handler
    def delete_workflows_from_definition(self, definition):
        for key in definition.keys():
            if key == "version":
                continue
            name = key
            res = self._security_request('DELETE',
                                         self._mistral_url +
                                         f"/workflows/{name}?namespace={self._workflow_namespace}")
            assert_response(res, [404, 204])

            try:
                self._workflows.remove(name)
            except ValueError as e:
                logger.debug(e)

    @error_handler
    def create_workbook(self, name):
        with open(process_workbook_file(name), 'r') as f:
            workflow_str = f.read()

        res = self._security_request('POST', self._mistral_url +
                                     f"/workbooks",
                                     data=workflow_str)
        assert_response(res, 201)

        self._workbooks.append(name)

    @error_handler
    def delete_workbook(self, name):
        res = self._security_request('DELETE',
                                     self._mistral_url +
                                     f"/workbooks/{name}")
        assert_response(res, [404, 204])

        try:
            self._workbooks.remove(name)
        except ValueError as e:
            logger.debug(e)

    @error_handler
    def take_off_refuses(self):
        logger.debug(f'Remove the following workflows: {self._workflows}')
        for wf in self._workflows.copy():
            retry(self.delete_workflow, wf)
        self._workflows = []

        logger.debug(f'Remove the following workbooks: {self._workbooks}')
        for wb in self._workbooks.copy():
            retry(self.delete_workbook, f"{wb}.{wb}")
        self._workbooks = []

        if self._ex_id:
            logger.debug(f'Remove the following executions: {self._ex_id}')
            retry(self.delete_execution)

    @error_handler
    def get_workflow(self, name):
        res = self._security_request('GET',
                                     self._mistral_url + f'/workflows/{name}?namespace={self._workflow_namespace}')
        assert_response(res, [200, 404])

        if res.status_code == 404:
            error_message = res.json()
            return error_message['faultstring']

        return res.json()

    def create_execution_with_file_input(self, name, input_file_name=None):
        with open(process_json_resource_file(input_file_name), 'r') as f:
            ex_input = f.read()

        res = self._create_execution_internal(name, ex_input)

        logger.debug(f'res.json(): {res.text}')

        assert_response(res, 400)
        res_json = res.json()

        raise Exception(extract_api_fault_string(res_json))

    @timeout()
    @error_handler
    def create_execution(self, name, ex_input=None, ex_id=None, params=None):
        res = self._create_execution_internal(
            name=name, ex_input=ex_input, ex_id=ex_id, params=params)

        if res.status_code == 423:
            return 423
        assert_response(res, 201)

        execution = res.json()
        self._ex_id = execution['id']

        logger.debug(f"Created execution {execution}")
        return execution

    def _create_execution_internal(self, name, ex_input=None, ex_id=None, params=None):
        ex_input = ex_input if ex_input else {}
        ex_id = ex_id if ex_id else str(uuid.uuid4())

        logger.debug(f'Workflow name: {name}. Execution input: {ex_input}. ' +
                     f'Execution id: {ex_id}. Params: {params}')

        json_params = {'workflow_name': name, 'id': ex_id}

        # workbook doesn't support namespaces
        if '.' not in name:
            json_params['workflow_namespace'] = self._workflow_namespace
        if ex_input:
            json_params['input'] = ex_input
        if params:
            json_params['params'] = params

        res = self._security_request('POST', self._mistral_url + '/executions',
                                     json=json_params)
        return res

    def get_execution(self, ex_id=None):
        if not ex_id:
            ex_id = self._ex_id

        res = self._security_request('GET',
                                     self._mistral_url + '/executions/'
                                     + ex_id)
        assert_response(res)

        return dotdict.DotDict(res.json())

    def get_execution_with_fields(self, ex_id=None, fields=''):
        if not ex_id:
            ex_id = self._ex_id

        if fields != '':
            fields = f"?fields={fields}"

        res = self._security_request('GET',
                                     self._mistral_url + '/executions/'
                                     + ex_id
                                     + fields)
        assert_response(res)

        return dotdict.DotDict(res.json())

    def get_execution_duration_info_by_name(self, wf_name):
        res = self._security_request(
            'GET',
            self._mistral_url + '/executions?workflow_name=' + wf_name
                              + '&fields=created_at,updated_at'
        )

        assert_response(res)

        return res.json()['executions']

    def get_tasks_duration_info_by_ex_id(self, ex_id):
        res = self._security_request(
            'GET',
            self._mistral_url + '/executions/' + ex_id
            + '/tasks?fields=started_at,finished_at'
        )

        assert_response(res)

        return res.json()['tasks']

    def get_all_executions(self):
        res = self._security_request('GET',
                                     self._mistral_url + '/executions')
        assert_response(res)

        return res.json()['executions']

    def get_all_workflows(self):
        res = self._security_request('GET',
                                     self._mistral_url + '/workflows')
        assert_response(res)

        return list(filter(lambda wf: wf['name'] not in SKIPPED_WORKFLOWS, res.json()['workflows']))

    def get_all_workbooks(self):
        res = self._security_request('GET',
                                     self._mistral_url + '/workbooks')
        assert_response(res)

        return res.json()['workbooks']

    def get_task(self, task_name):
        task = [x for x in self._get_tasks() if x['name'] == task_name][0]

        task_id = task['id']

        res = self._security_request('GET',
                                     self._mistral_url + '/tasks/'
                                     + task_id)
        assert_response(res)

        return dotdict.DotDict(res.json())

    @error_handler
    def create_executions_bulk(self, name, number, ex_input=None, params=None):
        for _ in range(int(number)):
            ex = retry(self.create_execution, name, ex_input=ex_input, params=params)

            self._ex_ids.add(ex['id'])

    @error_handler
    def wait_executions_bulk(self):
        for _ in range(2 * 40):
            try:
                executions_ids = []
                number_running_executions = 0
                for ex_id in self._ex_ids:
                    res = self._security_request('GET',
                                                 self._mistral_url + '/executions/'
                                                 + ex_id)
                    res.raise_for_status()

                    state = res.json()['state']
                    if state not in ['SUCCESS', 'ERROR', 'PAUSED']:
                        executions_ids.append(ex_id)
                        number_running_executions += 1

                if not number_running_executions:
                    return

                logger.error(f'Number of running executions: {number_running_executions}. '
                             f'Executions: [{", ".join(executions_ids)}]')
            except BaseException as e:
                logger.error(str(e))
            time.sleep(30)

        raise Exception('Time is over')

    @error_handler
    def validate_workflow_executions(self):
        is_valid = True
        not_valid_exs = []

        for ex_id in self._ex_ids:
            try:
                self._validate_parent_wf(ex_id)
            except BaseException as e:
                is_valid = False
                not_valid_exs.append(ex_id)

                logger.error(str(e))

        if not is_valid:
            raise Exception(f'The following workflow executions not valid: {not_valid_exs}')

    def _validate_parent_wf(self, ex_id: str):
        res = self._security_request('GET',
                                     self._mistral_url + '/executions/'
                                     + ex_id)
        ex = res.json()
        logger.debug(f'Parent execution: {ex}')

        if ex['state'] != 'SUCCESS':
            raise ExecutionException('Workflow execution must has SUCCESS state', wf_ex=ex)

        ex_output = json.loads(ex['output'])

        if len(ex_output) != NUMBER_OF_PARENT_TASKS:
            raise ExecutionException(f'The number of output must equal {NUMBER_OF_PARENT_TASKS}', wf_ex=ex)

        tasks = self._get_tasks(ex_id)
        logger.debug(f'Tasks of parent execution: {tasks}')

        if len(tasks) != NUMBER_OF_PARENT_TASKS:
            raise ExecutionException(f'The number of task must equal {NUMBER_OF_PARENT_TASKS}', wf_ex=ex)

        for task in tasks:
            task_name = task['name']
            if task['type'] == 'WORKFLOW':
                self._validate_child_wf(task_id=task['id'])

                if ex_output[task_name] != {"task1": "task1", "task2": "task2"}:
                    raise ExecutionException("Wrong output for execution", wf_ex=ex, task_ex=task)
            else:
                task_published = json.loads(task['published'])

                if isinstance(task_published[task_name], list):
                    # check with-items
                    self._check_with_items_task(task, ex_output)
                else:
                    self._check_task(task, ex_output)

    def _validate_child_wf(self, task_id: str):
        res = self._security_request('GET',
                                     self._mistral_url + '/executions?task_execution_id='
                                     + task_id)
        executions = res.json()
        logger.debug(f'Child execution: {executions}')

        if len(executions['executions']) != 1:
            raise ExecutionException('The number of child executions must equal 1')

        ex = executions['executions'][0]

        res = self._security_request('GET',
                                     self._mistral_url + '/executions/'
                                     + ex['id'])
        ex = res.json()

        if ex['state'] != 'SUCCESS':
            raise ExecutionException('Workflow execution must has SUCCESS state', wf_ex=ex)

        ex_output = json.loads(ex['output'])

        if len(ex_output) != NUMBER_OF_CHILD_TASKS:
            raise ExecutionException(f'The number of child ex output must equal {NUMBER_OF_CHILD_TASKS}', wf_ex=ex)

        tasks = self._get_tasks(ex['id'])
        logger.debug(f'Tasks of child execution: {tasks}')

        if len(tasks) != NUMBER_OF_CHILD_TASKS:
            raise ExecutionException(f'The number of task must equal {NUMBER_OF_CHILD_TASKS}', wf_ex=ex)

        for task in tasks:
            self._check_task(task, ex_output)

    def _check_with_items_task(self, task, ex_output):
        task_name = task['name']
        task_published = json.loads(task['published'])

        if len(task_published) != 1:
            raise ExecutionException('Task published must has 1 length', task_ex=task)

        if task_published[task_name] != ["x1", "x2", "x3", "x4", "x5"]:
            raise ExecutionException('Wrong task output', task_ex=task)

        if ex_output[task_name] != ["x1", "x2", "x3", "x4", "x5"]:
            raise ExecutionException('Wrong execution output', task_ex=task)

    def _check_task(self, task, ex_output):
        task_name = task['name']
        task_published = json.loads(task['published'])

        if len(task_published) != 1:
            raise ExecutionException('Task published must has 1 length', task_ex=task)

        if task_published[task_name] != task_name:
            raise ExecutionException('Wrong task output', task_ex=task)

        if ex_output[task_name] != task_name:
            raise ExecutionException('Wrong execution output', task_ex=task)

    @error_handler
    def check_all_execution_has_success_or_paused_state(self):
        error_ex = set()
        for ex_id in self._ex_ids:
            ex = self.get_execution(ex_id)
            state = ex['state']

            if state not in ['SUCCESS', 'PAUSED']:
                error_ex.add((ex_id, state))

        if error_ex:
            logger.error(f'These executions must be success or paused: {error_ex}')

    @error_handler
    def delete_execution(self):
        res = self._security_request(
            'GET',
            self._mistral_url + "/executions/" + self._ex_id
        ).json()

        if res["state"] not in ["SUCCESS", "ERROR", "CANCELLED"]:
            self._security_request(
                'PUT',
                self._mistral_url + "/executions/" + self._ex_id,
                json={'state': "CANCELLED"}
            )

        res = self._security_request('DELETE',
                                     self._mistral_url + "/executions/" +
                                     self._ex_id)
        assert_response(res, [404, 204])

    @error_handler
    def delete_existing_executions_by_name(self, name):
        res = self._security_request(
            'GET',
            self._mistral_url + "/executions?workflow_name=" + name
        ).json()

        for execution in res["executions"]:
            id = execution["id"]
            if execution["state"] not in ["SUCCESS", "ERROR", "CANCELLED"]:
                self._security_request(
                    'PUT',
                    self._mistral_url + "/executions/" + id,
                    json={'state': "CANCELLED"}
                )
            res = self._security_request('DELETE',
                                         self._mistral_url + "/executions/" +
                                         id)
            assert_response(res, [404, 204])

    @error_handler
    def wait_unit_execution_will_has_state(self, state, attempt=30, wait=2, seconds=0):
        if seconds > 0:
            attempt = int(seconds/10)
            wait = 10

        for _ in range(attempt):
            time.sleep(wait)

            try:
                res = self._security_request('GET',
                                             self._mistral_url + '/executions/'
                                             + self._ex_id, timeout=10)
                assert_response(res)

                ex = res.json()
                logger.debug(ex)

                if state == ex['state']:
                    return
            except BaseException as e:
                logger.error(str(e))

        raise Exception("Time is up. Execution is {ex_id}. State is {state}"
                        "".format(ex_id=self._ex_id, state=ex['state']))

    @error_handler
    def delete_execution_if_state_is_not(self, state):
        try:
            res = self._security_request('GET',
                                         self._mistral_url + '/executions/'
                                         + self._ex_id)
            assert_response(res)

            ex = res.json()
            logger.debug(ex)

            if state == ex['state']:
                return

            res = self._security_request('DELETE',
                                         self._mistral_url + "/executions/" +
                                         self._ex_id,
                                         json={'force': 'true'})
            assert_response(res, [404, 204])
        except BaseException as e:
            logger.error(str(e))

    @error_handler
    def execution_output(self, output):
        res = self._security_request('GET',
                                     self._mistral_url + '/executions/'
                                     + self._ex_id)
        assert_response(res)

        ex = res.json()
        ex_output = json.loads(ex['output'])
        logger.debug(f"Execution output: {ex_output}")

        for k, v in output.items():
            asserts.assert_equal(v, ex_output[k])

    @error_handler
    def execution_output_contains_key(self, key):
        res = self._security_request('GET',
                                     self._mistral_url + '/executions/'
                                     + self._ex_id)
        assert_response(res)

        ex = res.json()
        ex_output = json.loads(ex['output'])
        logger.debug(f"Execution output: {ex_output}")

        if key not in ex_output:
            raise KeyError(key)

    @error_handler
    def pause_execution(self):
        self._change_execution({'state': 'PAUSED'})

    @error_handler
    def resume_execution(self):
        self._change_execution({'state': 'RUNNING'})

    @error_handler
    def fail_execution(self):
        self._change_execution({'state': 'ERROR'})

    @error_handler
    def cancel_execution(self):
        self._change_execution({'state': 'CANCELLED', 'sync': False})

    @error_handler
    def set_execution_read_only(self):
        self._change_execution({'params': {'read_only': True}})

    @error_handler
    def interrupt_execution(self, recursive_terminate_flag):
        flag = recursive_terminate_flag == 'True'
        self._change_execution({'state': 'ERROR',
            'params': {'recursive_terminate': flag}})

    @error_handler
    def get_wf_ex_by_task(self, task_name):
        task = [x for x in self._get_tasks() if x['name'] == task_name][0]

        task_id = task['id']

        res = self._security_request(
            'GET',
            self._mistral_url + '/executions?task_execution_id=' + task_id)
        assert_response(res)

        ex = res.json()['executions'][0]

        return dotdict.DotDict(ex)

    def _change_execution(self, ex):
        res = self._security_request('PUT',
                                     self._mistral_url + '/executions/'
                                     + self._ex_id,
                                     json=ex)
        assert_response(res)

        ex = res.json()
        logger.debug(f"Execution: {ex}")

    @error_handler
    def number_of_tasks_equals(self, number_of_tasks):
        asserts.assert_equal(int(number_of_tasks), len(self._get_tasks()))

    @error_handler
    def number_of_actions_equals(self, task_name, number_of_actions):
        task = [x for x in self._get_tasks() if x['name'] == task_name][0]

        task_id = task['id']
        actions = self._get_actions(task_id)
        asserts.assert_equal(
            int(number_of_actions),
            len(actions),
            "Task id: {}. Actions: {}".format(task_id, actions)
        )

    @error_handler
    def task_param_equals(self, task_name, **kwargs):
        for task in self._get_tasks():
            if task['name'] != task_name:
                continue

            for task_k, task_v in kwargs.items():
                if task_k == 'output' or task_k == 'published':
                    task_param = json.loads(task[task_k])

                    for k, v in task_v.items():
                        asserts.assert_equal(v, task_param[k])
                else:
                    asserts.assert_equal(task_v, task[task_k],
                                         "Task attribute " + task_k)

            break

    @error_handler
    def skip_task(self, task_name):
        task = [x for x in self._get_tasks() if x['name'] == task_name][0]
        task_id = task['id']

        url = self._mistral_url + '/tasks'
        payload = {"id": task_id, "state": "SKIPPED"}

        res = self._security_request('PUT', url, json=payload)
        print("response = ")
        print(res)
        status_code = res.status_code
        assert_response(res, 200)

        return status_code

    @error_handler
    def continue_action(self, action_ex_id):
        body = {
            "state": 'SUCCESS'
        }
        res = self._security_request(
            'PUT',
            self._mistral_url + '/action_executions/' + action_ex_id,
            json=body)

        if res.status_code == 423:
            return 423

        res.raise_for_status()

    @error_handler
    def get_event_params(self, events, url, number_of_retries=None, polling_time=None):
        if not isinstance(events, list):
            return ValueError(f"{events} events must be list type")

        if not events:
            return ValueError(f"{events} events must not be empty")

        webhook_parameters = {
            "type": "webhook",
            "event_types": events,
            "url": url
        }

        if number_of_retries:
            webhook_parameters['number_of_retries'] = number_of_retries

        if polling_time:
            webhook_parameters['polling_time'] = polling_time

        return {"notify": [webhook_parameters]}

    @error_handler
    def get_event_noop_params(self, events):
        if not isinstance(events, list):
            return ValueError(f"{events} events must be list type")

        if not events:
            return ValueError(f"{events} events must not be empty")

        noop_parameters = {
            "type": "noop",
            "events": events
        }

        return {"notify": [noop_parameters]}

    @error_handler
    def get_action_definitions(self, name):
        res = self._security_request('GET', self._mistral_url +
                                     '/actions?name=has:{}'.format(
                                         name
                                     ))
        assert_response(res)

        return res.json()['actions']

    def _security_request(self, *args, **kwargs):
        headers = kwargs.get('headers')

        if self._auth_enable:
            if not headers:
                headers = {}

            headers['Authorization'] = 'Bearer ' + self.get_token()

            kwargs['headers'] = headers

        kwargs['timeout'] = 120

        res = requests.request(*args, **kwargs)
        logger.debug(res)
        return res

    def _get_tasks(self, ex_id=None):
        if not ex_id:
            ex_id = self._ex_id
        if ex_id:
            res = self._security_request(
                'GET',
                self._mistral_url + '/executions/' + ex_id +
                '/tasks')
            assert_response(res)

            return res.json()['tasks']

        if not self._tasks:
            res = self._security_request(
                'GET',
                self._mistral_url + '/executions/' + self._ex_id +
                '/tasks')
            assert_response(res)

            self._tasks = res.json()['tasks']

        return self._tasks

    def _get_actions(self, task_id):
        res = self._security_request(
            'GET',
            self._mistral_url + '/action_executions?task_execution_id=' +
            task_id)
        assert_response(res)

        return res.json()['action_executions']

    @error_handler
    def all_tasks_completed(self):
        res = self._security_request(
            'GET',
            self._mistral_url + '/executions/' + self._ex_id +
            '/tasks')
        assert_response(res)

        tasks = res.json()['tasks']

        for task in tasks:
            if task['state'] != 'SUCCESS':
                raise Exception(
                    'Task execution {} has not completed state'.format(
                        task['id']
                    ))

    @error_handler
    def set_maintenance_mode(self, status):
        a = parse.urlparse(self._mistral_url)
        url = a.scheme + '://' + a.netloc

        res = self._security_request(
            'PUT',
            url + '/maintenance', json={'status': status})
        logger.debug(res.text)
        res.raise_for_status()

        return dotdict.DotDict(res.json())

    @error_handler
    def get_maintenance_mode(self):
        a = parse.urlparse(self._mistral_url)
        url = a.scheme + '://' + a.netloc

        res = self._security_request(
            'GET',
            url + '/maintenance')

        return dotdict.DotDict(res.json())

    @error_handler
    def await_mistral_cluster_status(self, status, attempt=30, wait=2):
        for _ in range(attempt):
            time.sleep(wait)

            res_status = self.get_maintenance_mode()

            if res_status['status'] == status:
                return

        raise Exception('Time is up')

    @error_handler
    def wait_mistral_api(self):
        for _ in range(12 * 3):
            try:
                res = self._security_request('GET', self._mistral_url)
                status_code = res.status_code

                if status_code != 200:
                    raise Exception(f'Mistral API returns {status_code}')

                return
            except BaseException as e:
                logger.debug(str(e))

            time.sleep(5)

        raise Exception('Time is over')

    @error_handler
    def get_info(self):
        a = parse.urlparse(self._mistral_url)
        url = a.scheme + '://' + a.netloc

        res = requests.get(f'{url}' + '/info')
        res.raise_for_status()

        return utils.DotDict(res.json()['git'])

    @error_handler
    def wait_mistral_engine_and_executor(self):
        # timeout is 3 min
        timeout = time.time() + 600
        while True:
            try:
                if time.time() > timeout:
                    raise TimeoutError('Time is up')
                res = self._security_request('POST', f'{self._mistral_url}/action_executions',
                                             json={'name': 'std.sleep', 'input': {'seconds': '5'}})

                status_code = res.status_code
                if status_code not in [201, 401, 423]:
                    raise Exception(f'Mistral API returns {status_code}')

                if status_code == 201 and res.json()['state'] != 'SUCCESS':
                    raise Exception(f'Action [json={res.json()}] must have the SUCCESS state')

                return
            except TimeoutError as e:
                raise e
            except BaseException as e:
                logger.error(e)

                time.sleep(10)


if __name__ == '__main__':
    m = Mistral(mistral_url='http://localhost:8989/v2',
                auth_enable='f',
                client_register_token=None, idp_server=None,
                tenant=None, idp_user=None, idp_password=None,
                multitenancy_enabled='False', idp_client_id=None,
                idp_client_secret=None, workflow_namespace=None)
    print(m.wait_mistral_engine_and_executor())
