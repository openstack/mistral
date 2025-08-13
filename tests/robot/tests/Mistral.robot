# -*- coding: robot -*-

*** Variables ***
${OWN_URL}                 %{OWN_URL}
${AUTH_ENABLE}             %{AUTH_ENABLE}
${TENANT}                  system
${WORKFLOW_NAMESPACE}      tests
${KUBERNETES_NAMESPACE}    %{KUBERNETES_NAMESPACE}


*** Settings ***
Library  BuiltIn
Library  OperatingSystem
Library  ../lib/Mistral.py  mistral_url=%{MISTRAL_URL}
...                      auth_enable=%{AUTH_ENABLE}
...                      auth_type=%{AUTH_TYPE}
...                      client_register_token=%{CLIENT_REGISTRATION_TOKEN}
...                      idp_server=%{IDP_SERVER}
...                      tenant=${TENANT}
...                      idp_user=%{IDP_USER}
...                      idp_password=%{IDP_PASSWORD}
...                      idp_client_id=%{IDP_CLIENT_ID}
...                      idp_client_secret=%{IDP_CLIENT_SECRET}
...                      workflow_namespace=${WORKFLOW_NAMESPACE}
Library  ../lib/HttpServerLibrary.py  mistral_url=%{MISTRAL_URL}
Library  ../lib/UtilsLibrary.py
Library  PlatformLibrary  managed_by_operator=true
Library  String

Test Setup       Wait Until Keyword Succeeds  3 min  5 sec  Set maintenance mode  RUNNING
Test Teardown    Wait Until Keyword Succeeds  3 min  5 sec  Run Keywords
...                 Clear events
...          AND    Set maintenance mode  RUNNING
...          AND    Take off refuses
Suite Teardown   Wait Until Keyword Succeeds  3 min  5 sec  Set maintenance mode  RUNNING


*** Keywords ***
Recreate the ${name} workflow
    delete workflow     ${name}
    create workflow     ${name}

Recreate the ${name} workflow and start
    delete workflow     ${name}
    create workflow     ${name}

    create execution    ${name}

Recreate the ${name} workflow and start with ${input}
    delete workflow     ${name}
    create workflow     ${name}

    ${EX}=  create execution    ${name}  ex_input=${input}
    [Return]  ${EX}

Recreate ${name} workflow and start with input from ${file_name}
    delete workflow     ${name}
    create workflow     ${name}

    ${EX}=  create_execution_with_file_input    ${name}  input_file_name=${file_name}
    [Return]  ${EX}

Recreate the ${name} workflow and start params ${params}
    delete workflow     ${name}
    create workflow     ${name}

    create execution    ${name}  params=${params}

Recreate the ${name} workflow, start and wait ${state} state
    delete workflow     ${name}
    create workflow     ${name}

    create execution    ${name}
    Wait until the execution will has ${state} state

Recreate the ${name} workflow, start with ${input} and wait ${state} state
    delete workflow     ${name}
    create workflow     ${name}

    create execution    ${name}  ex_input=${input}
    Wait until the execution will has ${state} state

Recreate the ${name} workflow and starts with ${input} and params ${params}
    delete workflow     ${name}
    create workflow     ${name}

    ${EX}=  create execution    ${name}  ex_input=${input}  params=${params}

Recreate the ${name} workbook
    delete workbook     ${name}
    create workbook     ${name}

Wait until the execution will has ${state} state
    wait unit execution will has state  ${state}

${param} of ${name} task must be equal ${value}
    task param equals   ${name}     ${param}=${value}

Compare Images From Resources With Dd
    [Arguments]  ${dd_images}
    ${stripped_resources}=  Strip String  ${dd_images}  characters=,  mode=right
    @{list_resources} =  Split String	${stripped_resources} 	,
    FOR  ${resource}  IN  @{list_resources}
      ${type}  ${name}  ${container_name}  ${image}=  Split String	${resource}
      ${resource_image}=  Get Resource Image  ${type}  ${name}  ${KUBERNETES_NAMESPACE}  ${container_name}
      Should Be Equal  ${resource_image}  ${image}
    END

*** Test Cases ***
Basic execution is finished successfully
    [Tags]    basic
    Recreate the basic workflow, start and wait SUCCESS state

Sub workflow execution
    [Tags]    basic
    Recreate the sub_wf workflow
    Recreate the main_wf workflow, start and wait SUCCESS state

    ${SUB_EX}=  Get wf ex by task  task_name=task2
    Should be equal  SUCCESS  ${SUB_EX.state}

Failed sub workflow inside join task
    [Tags]    basic
    Recreate the failed_sub_wf workflow
    Recreate the join_main_wf workflow, start and wait ERROR state

    ${SUB_EX}=  Get wf ex by task  task_name=join_task
    Should be equal  ERROR  ${SUB_EX.state}

    state of join_task task must be equal ERROR

Basic error handling
    [Tags]    basic
    Recreate the ehf workflow, start and wait SUCCESS state

    number of tasks equals   3
    state of task1 task must be equal ERROR
    state of task2 task must be equal SUCCESS
    state of task4 task must be equal SUCCESS

With items task policy
    [Tags]    basic
    ${INPUT_LIST}=  Create List    aaa  bbb  ccc
    ${EX_INPUT}=    Create Dictionary   vm_names=${INPUT_LIST}

    Recreate the with_items workflow, start with ${EX_INPUT} and wait SUCCESS state

    state of task1 task must be equal SUCCESS
    number of actions equals    task1   1
    state of task2 task must be equal SUCCESS
    number of actions equals    task2   3

Join all task policy
    [Tags]    basic
    Recreate the join_all workflow, start and wait SUCCESS state

    number of tasks equals  6

Workflow with long task name shouldn't be created
    [Tags]  basic
    ${error_msg} =    Run Keyword And Expect Error    *   Recreate the long_task_name workflow
    Should Contain   ${error_msg}    task name must not exceed 255 symbols

Execution with huge input shouldn't be created
    [Tags]  basic  noncritical
    ${error_msg} =    Run Keyword And Expect Error    *   Recreate basic_with_input workflow and start with input from huge_execution_input

    Should Match   ${error_msg}    Field size limit exceeded [class=TaskExecution, field=input, size=*, limit=*

Workflow with a http action
    [Tags]  basic  http
    ${EX_INPUT}=    Create Dictionary   url=${OWN_URL}/sync

    Recreate the http_action workflow, start with ${EX_INPUT} and wait SUCCESS state

Workflow with a async http action
    [Tags]  basic  http
    ${EX_INPUT}=    Create Dictionary   url=${OWN_URL}/async

    Recreate the http_async_action workflow and start with ${EX_INPUT}

    ${ACTION_EX_ID}=  await rest
    continue action  ${ACTION_EX_ID}

    Wait until the execution will has SUCCESS state

Javascript action
    [Tags]    basic
    ${EX_INPUT}=  Create Dictionary  x=4  y=5
    ${EX_OUTPUT}=  Create Dictionary  z=45

    Recreate the js workflow, start with ${EX_INPUT} and wait SUCCESS state
    Execution output  ${EX_OUTPUT}

Javascript action with return object
    [Tags]    basic  new
    ${EX_INPUT}=  Create Dictionary  value=123
    ${EX_OUTPUT}=  Create Dictionary  res=123

    Recreate the js_2 workflow, start with ${EX_INPUT} and wait SUCCESS state
    Execution output  ${EX_OUTPUT}

Idempotent execution creation
    [Tags]  basic
    ${EX_ID}=  generate uuid

    Recreate the basic workflow
    ${EXECUITON}=  Create execution  basic  ex_id=${EX_ID}
    Dictionary Should Contain  ${EXECUITON}  state  PLANNED

    Wait until the execution will has SUCCESS state

    ${EXECUITON}=  Create execution  basic  ex_id=${EX_ID}
    Should Contain  ${EXECUITON}  state  SUCCESS

Yaql in a workflow
    [Tags]  basic
    ${EX_OUTPUT}=  Create Dictionary  res=xx yy xx

    Recreate the yaql workflow, start and wait SUCCESS state
    Execution output  ${EX_OUTPUT}

Jinja in a workflow
    [Tags]  basic
    ${EX_OUTPUT}=  Create Dictionary  res=xx yy xx

    Recreate the jinja workflow, start and wait SUCCESS state
    Execution output  ${EX_OUTPUT}

Workflow fail notifications
    [Tags]  basic  notifications
    ${EVENTS}=  Create List  WORKFLOW_FAILED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify

    Recreate the wf_fail_notification workflow and start params ${EX_PARAMS}

    ${EX_STATE}=  Await Rest
    Should be equal  ERROR  ${EX_STATE}

    Wait until the execution will has ERROR state

Workflow success notifications
    [Tags]  basic  notifications
    ${EVENTS}=  Create List  WORKFLOW_SUCCEEDED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify

    Recreate the wf_success_notification workflow and start params ${EX_PARAMS}

    ${EX_STATE}=  Await Rest
    Should be equal  SUCCESS  ${EX_STATE}

    Wait until the execution will has SUCCESS state

Workflow launch notifications
    [Tags]  basic  notifications
    ${EVENTS}=  Create List  WORKFLOW_LAUNCHED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify

    Recreate the wf_success_notification workflow and start params ${EX_PARAMS}

    ${EX_STATE}=  Await Rest
    Should be equal  RUNNING  ${EX_STATE}

    Wait until the execution will has SUCCESS state

Task fail notifications
    [Tags]  basic  notifications
    ${EVENTS}=  Create List  TASK_FAILED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify

    Recreate the wf_fail_notification workflow and start params ${EX_PARAMS}

    ${EX_STATE}=  Await Rest
    Should be equal  ERROR  ${EX_STATE}

    Wait until the execution will has ERROR state

Task success notifications
    [Tags]  basic  notifications
    ${EVENTS}=  Create List  TASK_SUCCEEDED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify

    Recreate the wf_success_notification workflow and start params ${EX_PARAMS}

    ${EX_STATE}=  Await Rest
    Should be equal  SUCCESS  ${EX_STATE}

    Wait until the execution will has SUCCESS state

Task launch notifications
    [Tags]  basic  notifications
    ${EVENTS}=  Create List  TASK_LAUNCHED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify

    Recreate the wf_success_notification workflow and start params ${EX_PARAMS}

    ${EX_STATE}=  Await Rest
    Should be equal  RUNNING  ${EX_STATE}

    Wait until the execution will has SUCCESS state

Workflow pause notifications
    [Tags]  basic  noncritical  notifications
    [Teardown]  Run keywords  clear events  AND
    ...         Delete execution
    ${EVENTS}=  Create List  WORKFLOW_PAUSED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify

    Recreate the wf_pause_notification workflow and start params ${EX_PARAMS}

    Wait until the execution will has RUNNING state

    Pause execution

    ${EX_STATE}=  Await Rest
    # TODO: Change to my plugin later
    Should be equal  PAUSED  ${EX_STATE}

    Wait until the execution will has PAUSED state

Webhook plugin sends notification
    [Tags]  basic  notifications
    ${EVENTS}=  Create List  TASK_SUCCEEDED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_retry_notify
    ...     polling_time=${2}
    Set fail number  ${0}

    Recreate the wf_success_notification workflow and start params ${EX_PARAMS}

    ${EX_STATE}=  Await rest
    Should be equal  SUCCESS  ${EX_STATE}

    Wait until the execution will has SUCCESS state

Return 401 status without token
    [Tags]  security

    ${STATUS_CODE}=  Get not exist workflow
    Should be equal  401  ${STATUS_CODE}

Succeed workflow command
    [Tags]  basic
    ${EX_INPUT}=  Create Dictionary  command=succeed

    Recreate the wf_command workflow, start with ${EX_INPUT} and wait SUCCESS state

    Number of tasks equals   1
    Task param equals  task1  state=SUCCESS

Fail workflow command
    [Tags]  basic
    ${EX_INPUT}=  Create Dictionary  command=failed

    Recreate the wf_command workflow, start with ${EX_INPUT} and wait ERROR state

    Number of tasks equals   1
    Task param equals  task1  state=SUCCESS

Pause workflow command
    [Tags]  basic
    ${EX_INPUT}=  Create Dictionary  command=paused

    Recreate the wf_command workflow, start with ${EX_INPUT} and wait PAUSED state

    Number of tasks equals   1
    Task param equals  task1  state=SUCCESS

Adhoc actions
    [Tags]  basic
    ${EX_INPUT}=  Create Dictionary  str1=a  str2=b
    ${EX_OUTPUT}=  Create Dictionary  workflow_result=a+b and a+b
    ...                               concat_task_result=a+b and a+b

    Recreate the adhoc_actions workbook
    Create execution  adhoc_actions.adhoc_actions  ex_input=${EX_INPUT}
    Wait until the execution will has SUCCESS state

    Execution output  ${EX_OUTPUT}

Parallel branches
    [Tags]  basic
    ${TASK1_OUTPUT}=  Create Dictionary  var1=aa
    ${TASK2_OUTPUT}=  Create Dictionary  var2=bb

    Recreate the parallel_branches workflow, start and wait SUCCESS state

    Number of tasks equals   2
    Task param equals  task1  published=${TASK1_OUTPUT}
    Task param equals  task2  published=${TASK2_OUTPUT}

Publish on-error
    [Tags]  basic
    ${TASK_OUTPUT}=  Create Dictionary  hi=hello_from_error
    ${EX_OUTPUT}=  Create Dictionary  out=hello_from_error

    Recreate the publish_on_error workflow, start and wait ERROR state
    Execution output  ${EX_OUTPUT}
    Execution output  ${EX_OUTPUT}

    Number of tasks equals   1
    Task param equals  task1  published=${TASK_OUTPUT}

Start workflow inside task
    [Tags]  basic
    ${TASK_OUTPUT}=  Create Dictionary  var=stub

    Recreate the child workflow
    Recreate the parent workflow, start and wait SUCCESS state

    Number of tasks equals   1
    Task param equals  task1  published=${TASK_OUTPUT}

DR pause mode
    [Tags]  dr
    ${EVENTS}=  Create List  WORKFLOW_LAUNCHED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify
    Recreate the pause_mode workflow and start params ${EX_PARAMS}
    ${EX_STATE}=  Await Rest

    ${STATE}=  Get maintenance mode
    Should be equal  RUNNING  ${STATE.status}

    Sleep  10s

    ${MISTRAL_STATE}=  Set maintenance mode  PAUSED
    Should be equal  PAUSING  ${MISTRAL_STATE.status}

    ${MISTRAL_STATE}=  Get maintenance mode
    Should be equal  PAUSING  ${MISTRAL_STATE.status}

    Await mistral cluster status  PAUSED

    Wait until the execution will has PAUSED state
    All tasks completed

    ${STATUS_CODE}=  Create execution  pause_mode
    Should be equal  ${423}  ${STATUS_CODE}

    # Check idempotent method
    ${MISTRAL_STATE}=  Set maintenance mode  PAUSED
    Should be equal  PAUSED  ${MISTRAL_STATE.status}
    Await mistral cluster status  PAUSED

    ${STATUS_CODE}=  Create execution  pause_mode
    Should be equal  ${423}  ${STATUS_CODE}

    ${STATUS_CODE}=  Create workflow  basic
    Should be equal  ${423}  ${STATUS_CODE}

    ${MISTRAL_STATE}=  Set maintenance mode  RUNNING
    Should be equal  RUNNING  ${MISTRAL_STATE.status}
    ${STATE}=  Get maintenance mode
    Should be equal  RUNNING  ${STATE.status}

    # Check idempotent method
    ${MISTRAL_STATE}=  Set maintenance mode  RUNNING
    Should be equal  RUNNING  ${MISTRAL_STATE.status}
    ${STATE}=  Get maintenance mode
    Should be equal  RUNNING  ${STATE.status}

    # Automaticly resume execution
    wait unit execution will has state  SUCCESS  attempt=${70}

    Recreate the basic workflow, start and wait SUCCESS state

Async action with pause mode
    [Tags]  dr  basic
    ${EVENTS}=  Create List  WORKFLOW_LAUNCHED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify
    ${EX_INPUT}=  Create Dictionary  url=${OWN_URL}/async

    Recreate the http_async_action workflow and starts with ${EX_INPUT} and params ${EX_PARAMS}
    ${EX_STATE}=  await status

    ${STATE}=  Get maintenance mode
    Should be equal  RUNNING  ${STATE.status}

    Set maintenance mode  PAUSED
    Await mistral cluster status  PAUSING

    Sleep  10s

    ${ACTION_EX_ID}=  await action id
    Wait Until Keyword Succeeds  10x  2s  continue action  ${ACTION_EX_ID}

    Await mistral cluster status  PAUSED
    ${HTTP_CODE}=  continue action  ${ACTION_EX_ID}
    Should be equal  ${423}  ${HTTP_CODE}

    Wait until the execution will has PAUSED state
    Await mistral cluster status  PAUSED
    All tasks completed

Dry Run Openstack
    [Tags]  custom-actions
    ${EX_INPUT}=     Create Dictionary  name=test
    ...              image_id=a2126651-2d3f-4470-a12e-70831413acb1
    ...              flavor_id=95f67ec0-788b-4655-baa0-36647fd5f45b
    ${EX_OUTPUT}=    Create Dictionary  id=a2126651-2d3f-4470-a12e-70831413acb1

    Recreate the dry_run_openstack workflow and start with ${EX_INPUT}

    Wait until the execution will has SUCCESS state
    Execution output  ${EX_OUTPUT}

Canceled execution during pause mode
    [Tags]  dr

    Recreate the pause_mode workflow and start

    ${STATE}=  Get maintenance mode
    Should be equal  RUNNING  ${STATE.status}

    Sleep  10s

    Set maintenance mode  PAUSED
    Await mistral cluster status  PAUSED

    Wait until the execution will has PAUSED state
    All tasks completed

    Cancel execution
    Wait until the execution will has CANCELLED state

Check the meow custom action
    [Tags]  custom-actions
    ${EX_OUTPUT}=  Create Dictionary  result=meow

    Recreate the wf_meow workflow, start and wait SUCCESS state
    Execution output  ${EX_OUTPUT}

Check the meow custom action with input
    [Tags]  custom-actions
    ${EX_OUTPUT}=  Create Dictionary  result=burk

    Recreate the wf_meow_with_input workflow, start and wait SUCCESS state
    Execution output  ${EX_OUTPUT}

There are test_nova actions
    [Tags]  custom-actions

    ${ACTIONS}=  Get action definitions  test_nova
    Should Be True  len(${ACTIONS}) > 100

Get token from action
    [Tags]  custom-actions

    Recreate the action_token workflow, start and wait SUCCESS state

    Execution output contains key  access_token

Check valid json in state_info
    [Tags]  basic
    Recreate the state_info workflow, start and wait ERROR state

    ${EX}=  Get execution
    Should be equal  {"abc0": "pqr"}  ${EX.state_info}

Duplicate creation of a workflow must return 401 code
    [Tags]  basic
    delete workflow  basic

    ${HTTP_STATUS_CODE}=  create workflow  basic
    Should be equal  ${201}  ${HTTP_STATUS_CODE}

    ${HTTP_STATUS_CODE}=  create workflow  basic
    Should be equal  ${409}  ${HTTP_STATUS_CODE}

Workflow with a oauth2 http action returns token
    [Tags]  basic  http
    Skip if auth is disalbed  ${AUTH_ENABLE}

    ${EX_INPUT}=    Create Dictionary   url=${OWN_URL}/oauth2

    Recreate the oauth2_http_action workflow, start with ${EX_INPUT} and wait SUCCESS state

    ${TOKEN}=  await rest
    Should Be True  '${TOKEN}' is not ${None}
    Should Be True  '${TOKEN}' != ""

Workflow with a oauth2 async http action returns token
    [Tags]  basic  http
    Skip if auth is disalbed  ${AUTH_ENABLE}

    ${EX_INPUT}=    Create Dictionary   url=${OWN_URL}/async_oauth2

    Recreate the oauth2_http_async_action workflow and start with ${EX_INPUT}

    ${ACTION_EX_ID}=  await rest
    continue action  ${ACTION_EX_ID}

    # TODO: fix later
#    ${TOKEN}=  await rest
#    Should Be True  '${TOKEN}' is not ${None}
#    Should Be True  '${TOKEN}' != ""

    Wait until the execution will has SUCCESS state

Workflow with a oauth2 http action
    [Tags]  basic  http

    ${EX_INPUT}=    Create Dictionary   url=${OWN_URL}/sync

    Recreate the oauth2_http_action workflow, start with ${EX_INPUT} and wait SUCCESS state

Workflow with a oauth2 async http action
    [Tags]  basic  http

    ${EX_INPUT}=    Create Dictionary   url=${OWN_URL}/async

    Recreate the oauth2_http_async_action workflow and start with ${EX_INPUT}

    ${ACTION_EX_ID}=  await rest
    continue action  ${ACTION_EX_ID}

    Wait until the execution will has SUCCESS state

Webhook notifier returns token
    [Tags]  basic  notifications

    Skip if auth is disalbed  ${AUTH_ENABLE}
    ${EVENTS}=  Create List  WORKFLOW_SUCCEEDED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/oauth2

    Recreate the wf_success_notification workflow and start params ${EX_PARAMS}

    ${TOKEN}=  await rest
    Should Be True  '${TOKEN}' is not ${None}
    Should Be True  '${TOKEN}' != ""

    Wait until the execution will has SUCCESS state

Mistral heartbeat
    [Tags]  basic  heartbeat

    Recreate the exit workflow and start

    wait unit execution will has state  state=ERROR  attempt=${48}  wait=${5}

Info REST
    [Tags]  basic
    ${GIT}=  get info

    should not be equal  ${GIT.id}  ${None}
    should not be equal  ${GIT.id}  ${EMPTY}

    should not be equal  ${GIT.time}  ${None}
    should not be equal  ${GIT.time}  ${EMPTY}

    should not be equal  ${GIT.branch}  ${None}
    should not be equal  ${GIT.branch}  ${EMPTY}

Execution with list of fields REST
    [Tags]  basic
    Recreate the basic workflow, start and wait SUCCESS state

    ${EX}=  get execution with fields  fields=state
    length should be  ${EX}  2
    should contain  ${EX}  state
    should not contain  ${EX}  workflow_id

    ${EX}=  get execution with fields  fields=state,workflow_id
    length should be  ${EX}  3
    should contain  ${EX}  state
    should contain  ${EX}  workflow_id

Task skip with publish and on skip branch
    [Tags]    basic
    ${TASK_OUTPUT}=  Create Dictionary  hi=hello_from_skip

    Recreate the task_skip_with_on_skip workflow, start and wait ERROR state
    number of tasks equals   1
    state of task1 task must be equal ERROR
    skip task  task1
    Wait until the execution will has SUCCESS state
    number of tasks equals   2
    state of task1 task must be equal SKIPPED
    state of task2 task must be equal SUCCESS
    Task param equals  task1  published=${TASK_OUTPUT}

Task skip with on success branch and without publish
    [Tags]    basic
    Recreate the task_skip_with_on_success workflow, start and wait ERROR state
    number of tasks equals   1
    state of task1 task must be equal ERROR
    skip task  task1
    Wait until the execution will has SUCCESS state
    number of tasks equals   2
    state of task1 task must be equal SKIPPED
    state of task2 task must be equal SUCCESS

Task skip with retry policy
    [Tags]    basic
    Recreate the task_skip_with_retry workflow, start and wait ERROR state
    number of tasks equals   1
    state of task1 task must be equal ERROR
    skip task  task1
    Wait until the execution will has SUCCESS state
    number of tasks equals   2
    state of task1 task must be equal SKIPPED
    state of task2 task must be equal SUCCESS

Workflows with spaces in their names cannot be created
    [Tags]  basic
    ${error_msg} =    Run Keyword And Expect Error    *   Recreate the test_spaces workflow
    Should Contain   ${error_msg}    Name 'test spaces' must not contain spaces

Executions with read_only flag cannot be updated
    [Tags]  basic
    Recreate the wf_fail_notification workflow, start and wait ERROR state
    set execution read only

    ${error_msg} =    Run Keyword And Expect Error    *   cancel execution
    Should contain  ${error_msg}  This execution is read only. Any update operation is forbidden

Retry policies are supported
    [Tags]  basic
    Recreate the retry_flow workflow, start and wait ERROR state
    number of actions equals  task1  4


The input field in execution responds
    [Tags]   basic
    Recreate the test_input_field workflow and start with {"context": "test_input"}
    Wait until the execution will has SUCCESS state
    ${TASK}=  get task  task1
    Should contain  ${TASK.result}  "test_input"

Tags was set and store
    [Tags]   basic
    Recreate the test_tags workflow, start and wait SUCCESS state
    ${EX}=  get execution
    ${TASK}=  get task  task1
    Should contain  ${EX.tags}  operation
    Should contain  ${TASK.tags}  sub-operation

Execution was cancelled
    [Tags]   basic
    ${EVENTS}=  Create List  WORKFLOW_LAUNCHED
    ${EX_PARAMS}=  Get Event Params  ${EVENTS}  url=${OWN_URL}/wf_notify
    Recreate the sleep_action workflow and start params ${EX_PARAMS}
    ${EX_STATE}=  Await Rest

    cancel execution
    Wait until the execution will has CANCELLED state
    number of tasks equals   1
    state of task1 task must be equal SUCCESS

Test Hardcoded Images
    [Tags]  mistral_images  basic
    ${dd_images}=  Get Dd Images From Config Map  tests-config  ${KUBERNETES_NAMESPACE}
    Skip If  '${dd_images}' == '${None}'  There is no deployDescriptor, not possible to check case!
    Compare Images From Resources With Dd  ${dd_images}
