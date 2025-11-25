# -*- coding: robot -*-

*** Variables ***
${TENANT}                 system
${WORKFLOW_NAMESPACE}  tests

*** Settings ***
Library  BuiltIn
Library  OperatingSystem
Library  ../lib/WorkflowGenerator.py
Library  ../lib/Mistral.py  mistral_url=%{MISTRAL_URL}
...                      auth_enable=%{AUTH_ENABLE}
...                      client_register_token=%{CLIENT_REGISTRATION_TOKEN}
...                      idp_server=%{IDP_SERVER}
...                      tenant=${TENANT}
...                      idp_user=%{IDP_USER}
...                      idp_password=%{IDP_PASSWORD}
...                      idp_client_id=%{IDP_CLIENT_ID}
...                      idp_client_secret=%{IDP_CLIENT_SECRET}
...                      workflow_namespace=${WORKFLOW_NAMESPACE}

Test Teardown    Run Keywords
...                 Take off refuses
...     AND         sleep  15


*** Keywords ***
Create ${wf_name} workflow by definition ${wf_def}, execute and wait ${seconds} seconds for finish
    create workflow by json definition  ${wf_def}
    create execution    ${wf_name}
    wait unit execution will has state  SUCCESS  seconds=${seconds}


*** Test Cases ***
Run parallel wf with joins 5x5
    [Tags]  mistral_svt  delayed_calls  smoke
    ${WF_NAME}  ${WF_DEF} =  generate parallel wf with joins
    ...                      branch_count=5  branch_length=5
    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 60 seconds for finish

Run parallel wf with joins 10x10
    [Tags]  mistral_svt  delayed_calls
    ${WF_NAME}  ${WF_DEF} =  generate parallel wf with joins
    ...                      branch_count=10  branch_length=10

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 240 seconds for finish

Run parallel wf with joins 20x10
    [Tags]  mistral_svt  delayed_calls
    ${WF_NAME}  ${WF_DEF} =  generate parallel wf with joins
    ...                      branch_count=20  branch_length=10

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 420 seconds for finish

Run parallel wf with joins 50x5
    [Tags]  mistral_svt  delayed_calls
    ${WF_NAME}  ${WF_DEF} =  generate parallel wf with joins
    ...                      branch_count=50  branch_length=5

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 900 seconds for finish

Run wf with context merging 100x10
    [Tags]  mistral_svt  context_merge
    ${WF_NAME}  ${WF_DEF} =  generate wf with context merge
    ...          branch_count=10  branch_length=10
    ...          data_count=100    data_length=10

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 420 seconds for finish

Run wf with context merging 100x1000
    [Tags]  mistral_svt  context_merge  smoke
    ${WF_NAME}  ${WF_DEF} =  generate wf with context merge
    ...          branch_count=10  branch_length=10
    ...          data_count=100    data_length=1000

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 900 seconds for finish

Run wf with context merging 1000x100
    [Tags]  mistral_svt  context_merge  benchmark_skip
    ${WF_NAME}  ${WF_DEF} =  generate wf with context merge
    ...          branch_count=10  branch_length=10
    ...          data_count=1000   data_length=100

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 900 seconds for finish

Run wf with nested wfs 1x50
    [Tags]  mistral_svt  nested_wfs  smoke
    ${WF_NAME}  ${WF_DEF} =  generate wf with nested wfs
    ...                      task_count=1  depth=50

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 120 seconds for finish

Run wf with nested wfs 1x100
    [Tags]  mistral_svt  nested_wfs
    ${WF_NAME}  ${WF_DEF} =  generate wf with nested wfs
    ...                      task_count=1  depth=100

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 300 seconds for finish

Run wf with nested wfs 1x300
    [Tags]  mistral_svt  nested_wfs
    ${WF_NAME}  ${WF_DEF} =  generate wf with nested wfs
    ...                      task_count=1  depth=300

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 300 seconds for finish

Run wf with nested wfs 2x10
    [Tags]  mistral_svt  nested_wfs  benchmark_skip
    ${WF_NAME}  ${WF_DEF} =  generate wf with nested wfs
    ...                      task_count=2  depth=10

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 900 seconds for finish

Run wf with nested wfs 3x7
    [Tags]  mistral_svt  nested_wfs  benchmark_skip
    ${WF_NAME}  ${WF_DEF} =  generate wf with nested wfs
    ...                      task_count=3  depth=7

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 1200 seconds for finish

Run wf with items 200x1
    [Tags]  mistral_svt  nested_wfs
    ${WF_NAME}  ${WF_DEF} =  generate wf with items
    ...                      with_items_count=200  concurrency=1

    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 1200 seconds for finish

Run wf with items 500x10
    [Tags]  mistral_svt  nested_wfs
    ${WF_NAME}  ${WF_DEF} =  generate wf with items
    ...                      with_items_count=500  concurrency=10
    Create ${WF_NAME} workflow by definition ${WF_DEF}, execute and wait 1200 seconds for finish