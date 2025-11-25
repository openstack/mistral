*** Variables ***
${ALERT_RETRY_TIME}                      5min
${ALERT_RETRY_INTERVAL}                  5s
${KUBERNETES_NAMESPACE}                  %{KUBERNETES_NAMESPACE}

*** Settings ***
Library  MonitoringLibrary  host=%{PROMETHEUS_URL}
Library  PlatformLibrary  managed_by_operator=true
Library  Collections
Library    String
Library  ../lib/kubernetes_utils.py

*** Keywords ***
Check Alert Status
    [Arguments]  ${alert_name}  ${exp_status}
    ${status}=  Get Alert Status  ${alert_name}  ${KUBERNETES_NAMESPACE}
    Should Be Equal As Strings  ${status}  ${exp_status}

Check That Prometheus Alert Is Active
    [Arguments]  ${alert_name}
    Wait Until Keyword Succeeds  ${ALERT_RETRY_TIME}  ${ALERT_RETRY_INTERVAL}
    ...  Check Alert Status  ${alert_name}  pending

Check That Prometheus Alert Is Inactive
    [Arguments]  ${alert_name}
    Wait Until Keyword Succeeds  ${ALERT_RETRY_TIME}  ${ALERT_RETRY_INTERVAL}
    ...  Check Alert Status  ${alert_name}  inactive

Scale Down Deployment
    [Arguments]  ${deployment_name}
    ${replicas}=  Set Variable  1
    Set Test Variable  ${replicas}
    ${deployment}=  Get Deployment Entity  ${deployment_name}  ${KUBERNETES_NAMESPACE}
    ${replicas}=  Set Variable  ${deployment.spec.replicas}
    Set Test Variable  ${replicas}
    Set Replicas For Deployment Entity  ${deployment_name}  ${KUBERNETES_NAMESPACE}  replicas=0

Scale Up Deployment
    [Arguments]  ${deployment_name}
    Set Replicas For Deployment Entity  ${deployment_name}  ${KUBERNETES_NAMESPACE}  replicas=${replicas}

Scale Down Resources
    [Arguments]  ${deployment_name}
    ${old_resources}=    Get Deployment Resources  ${deployment_name}  ${KUBERNETES_NAMESPACE}
    Set Test Variable  ${old_resources}
    Patch Deployment Resources  ${deployment_name}  ${KUBERNETES_NAMESPACE}

Scale Up Resources
    [Arguments]  ${deployment_name}
    Sleep    10s
    Patch Deployment Resources  ${deployment_name}  ${KUBERNETES_NAMESPACE}    ${old_resources}

*** Test Cases ***
Executor Is Degraded Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-executor
    ${alert_name}=   Set Variable   MistralExecutorDegraded
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Resources  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Resources  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}

Notifier Is Degraded Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-notifier
    ${alert_name}=   Set Variable   MistralNotifierDegraded
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Resources  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Resources  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}

Engine Is Degraded Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-engine
    ${alert_name}=   Set Variable   MistralEngineDegraded
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Resources  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Resources  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}

Monitoring Is Degraded Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-monitoring
    ${alert_name}=   Set Variable   MistralMonitoringDegraded
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Resources  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Resources  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}

API Is Degraded Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-api
    ${alert_name}=   Set Variable   MistralAPIDegraded
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Resources  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Resources  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}

Executor Is Down Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-executor
    ${alert_name}=   Set Variable   MistralExecutorDown
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Deployment  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Deployment  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}

Notifier Is Down Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-notifier
    ${alert_name}=   Set Variable   MistralNotifierDown
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Deployment  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Deployment  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}

Engine Is Down Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-engine
    ${alert_name}=   Set Variable   MistralEngineDown
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Deployment  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Deployment  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}

Monitoring Is Down Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-monitoring
    ${alert_name}=   Set Variable   MistralMonitoringDown
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Deployment  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Deployment  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}

API Is Down Alert
    [Tags]  alerts
    ${deployment_name}=   Set Variable   mistral-api
    ${alert_name}=   Set Variable   MistralAPIDown
    Check That Prometheus Alert Is Inactive  ${alert_name}
    Scale Down Deployment  ${deployment_name}
    Check That Prometheus Alert Is Active  ${alert_name}
    [Teardown]  Run Keywords
                ...  Scale Up Deployment  ${deployment_name}
                ...  AND  Check That Prometheus Alert Is Inactive  ${alert_name}