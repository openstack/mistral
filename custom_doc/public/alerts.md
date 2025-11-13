# Prometheus Alerts

## MistralAPIDegraded

### Description

Mistral API degraded, there are unavailable API pods.

### Possible Causes

- API pod failures or unavailability.
- Resource constraints impacting API pod performance.

### Impact

- Reduced or disrupted functionality of the Mistral API.
- Potential impact on workflows and automation processes relying on the API.

### Actions for Investigation

1. Check the status of Mistral API pods.
2. Review logs for Mistral API pods for any errors or issues.
3. Verify resource utilization of API pods (CPU, memory).

### Recommended Actions to Resolve Issue

1. Restart or redeploy Mistral API pods if they are in a failed state.
2. Investigate and address any resource constraints affecting the API pod performance.
---

## MistralAPIDown

### Description

Mistral API is down, and there are no available API pods.

### Possible Causes

- Network issues affecting the API pod communication.
- Mistral API service or pod failures.

### Impact

- Complete unavailability of the Mistral API.
- Workflows and automation processes relying on the API will fail.

### Actions for Investigation

1. Check the network connectivity to the Mistral API pods.
2. Verify the status and logs of Mistral API pods.

### Recommended Actions to Resolve Issue

1. Investigate and resolve network issues if detected.
2. Restart or redeploy Mistral API pods if necessary.
---

## MistralAPICPULoad

### Description

Mistral API uses 90% of the CPU limit.

### Possible Causes

- Inadequate CPU resources allocated to Mistral API pods.
- The service is overloaded.

### Impact

- Increased response time and potential slowdown of API requests.
- Degraded performance for workflows and automation processes using the API.

### Actions for Investigation

1. Monitor the CPU usage trends in Mistral API pods.
2. Review Mistral API logs for any performance related issues.

### Recommended Actions to Resolve Issue

1. Scale up Mistral API pods if needed.
---

## MistralAPIMemoryLoad

### Description

Mistral API uses 90% of the memory limit.

### Possible Causes

- Memory leaks or excessive memory consumption by the Mistral API.
- Insufficient memory resources allocated to Mistral API pods.

### Impact

- Potential out-of-memory errors and API instability.
- Degraded performance for workflows and automation processes using the API.

### Actions for Investigation

1. Monitor memory usage trends in Mistral API pods.
2. Review Mistral API logs for memory related errors.

### Recommended Actions to Resolve Issue

1. Scale up Mistral API pods if needed.
2. Investigate and address any memory leaks in the Mistral API code.
---

## MistralEngineDegraded

### Description

Mistral Engine degraded, there are unavailable Engine pods.

### Possible Causes

- Engine pod failures or unavailability.
- Resource constraints impacting the Engine pod performance.

### Impact

- Reduced or disrupted workflow execution and processing.
- Potential delays in automation tasks.

### Actions for Investigation

1. Check the status of Mistral Engine pods.
2. Review logs for Mistral Engine pods for any errors or issues.
3. Verify resource utilization of the Engine pods (CPU, memory).

### Recommended Actions to Resolve Issue

1. Restart or redeploy Mistral Engine pods if they are in a failed state.
2. Investigate and address any resource constraints affecting the Engine pod performance.
---

## MistralEngineDown

### Description

Mistral Engine is down, and there are no available Engine pods.

### Possible Causes

- Network issues affecting the Engine pod communication.
- Mistral Engine service or pod failures.

### Impact

- Complete unavailability of the Mistral Engine.
- Workflow execution and automation tasks relying on the Engine will fail.

### Actions for Investigation

1. Check the network connectivity to the Mistral Engine pods.
2. Verify the status and logs of Mistral Engine pods.

### Recommended Actions to Resolve Issue

1. Investigate and resolve network issues if detected.
2. Restart or redeploy Mistral Engine pods if necessary.
---

## MistralEngineOverloaded

### Description

Mistral Engine overloaded, there are lots of unprocessed RPC messages.

### Possible Causes

- High workload causing a backlog of RPC messages.
- Inefficient handling of RPC messages in Mistral Engine.

### Impact

- Delays in the workflow processing and execution.
- Potential workflow failures due to excessive RPC message backlog.

### Actions for Investigation

1. Monitor the rate of incoming RPC messages to Mistral Engine.
2. Review Mistral Engine logs for errors related to RPC message processing.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Engine pods to handle the increased workload if necessary.
---

## MistralEngineCPULoad

### Description

Mistral Engine uses 90% of the CPU limit.

### Possible Causes

- Inadequate CPU resources allocated to Mistral Engine pods.
- The service is overloaded.

### Impact

- Increased response time and potential slowdown of the workflow execution.
- Degraded performance for automation tasks relying on the Engine.

### Actions for Investigation

1. Monitor CPU usage trends in Mistral Engine pods.
2. Review Mistral Engine logs for any performance related issues.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Engine pods if needed.
---

## MistralEngineMemoryLoad

### Description

Mistral Engine uses 90% of the memory limit.

### Possible Causes

- Memory leaks or excessive memory consumption by Mistral Engine.
- Insufficient memory resources allocated to Mistral Engine pods.

### Impact

- Potential out-of-memory errors and Engine instability.
- Degraded performance for automation tasks relying on the Engine.

### Actions for Investigation

1. Monitor memory usage trends in Mistral Engine pods.
2. Review Mistral Engine logs for memory related errors.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Engine pods if needed.
2. Investigate and address any memory leaks in the Mistral Engine code.
---

## MistralExecutorDegraded

### Description

Mistral Executor degraded, there are unavailable Executor pods.

### Possible Causes

- Executor pod failures or unavailability.
- Resource constraints impacting the Executor pod performance.

### Impact

- Reduced or disrupted execution of workflow tasks.
- Potential delays in automation tasks relying on the Executor.

### Actions for Investigation

1. Check the status of Mistral Executor pods.
2. Review logs for Mistral Executor pods for any errors or issues.
3. Verify resource utilization of the Executor pods (CPU, memory).

### Recommended Actions to Resolve Issue

1. Restart or redeploy Mistral Executor pods if they are in a failed state.
2. Investigate and address any resource constraints affecting the Executor pod performance.
---

## MistralExecutorDown

### Description

Mistral Executor is down, and there are no available Executor pods.

### Possible Causes

- Network issues affecting the Executor pod communication.
- Mistral Executor service or pod failures.

### Impact

- Complete unavailability of the Mistral Executor.
- Workflow task execution and automation tasks relying on the Executor will fail.

### Actions for Investigation

1. Check the network connectivity to the Mistral Executor pods.
2. Verify the status and logs of the Mistral Executor pods.

### Recommended Actions to Resolve Issue

1. Investigate and resolve network issues if detected.
2. Restart or redeploy Mistral Executor pods if necessary.
---

## MistralExecutorOverloaded

### Description

Mistral Executor overloaded, there are lots of unprocessed RPC messages.

### Possible Causes

- High workload causing a backlog of RPC messages.
- Inefficient handling of RPC messages in Mistral Executor.

### Impact

- Delays in task execution and workflow processing.
- Potential task failures due to excessive RPC message backlog.

### Actions for Investigation

1. Monitor the rate of incoming RPC messages to Mistral Executor.
2. Review Mistral Executor logs for errors related to the RPC message processing.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Executor pods to handle the increased workload if necessary.
---

## MistralExecutorCPULoad

### Description

Mistral Executor uses 90% of the CPU limit.

### Possible Causes

- Inadequate CPU resources allocated to Mistral Executor pods.
- The service is overloaded.

### Impact

- Increased response time and potential slowdown of task execution.
- Degraded performance for automation tasks relying on the Executor.

### Actions for Investigation

1. Monitor CPU usage trends in Mistral Executor pods.
2. Review Mistral Executor logs for any performance related issues.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Executor pods if needed.
---

## MistralExecutorMemoryLoad

### Description

Mistral Executor uses 90% of the memory limit.

### Possible Causes

- Memory leaks or excessive memory consumption by Mistral Executor.
- Insufficient memory resources allocated to Mistral Executor pods.

### Impact

- Potential out-of-memory errors and Executor instability.
- Degraded performance for automation tasks relying on the Executor.

### Actions for Investigation

1. Monitor memory usage trends in Mistral Executor pods.
2. Review Mistral Executor logs for memory related errors.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Executor pods if needed.
2. Investigate and address any memory leaks in the Mistral Executor code.
---

## MistralNotifierDegraded

### Description

Mistral Notifier degraded, there are unavailable Notifier pods.

### Possible Causes

- Notifier pod failures or unavailability.
- Resource constraints impacting Notifier pod performance.

### Impact

- Reduced or disrupted notification and event handling.
- Potential delays in notifying stakeholders and executing actions.

### Actions for Investigation

1. Check the status of Mistral Notifier pods.
2. Review logs for Mistral Notifier pods for any errors or issues.
3. Verify resource utilization of the Notifier pods (CPU, memory).

### Recommended Actions to Resolve Issue

1. Restart or redeploy Mistral Notifier pods if they are in a failed state.
2. Investigate and address any resource constraints affecting the Notifier pod performance.
---

## MistralNotifierDown

### Description

Mistral Notifier is down, and there are no available Notifier pods.

### Possible Causes

- Network issues affecting the Notifier pod communication.
- Mistral Notifier service or pod failures.

### Impact

- Complete unavailability of the Mistral Notifier.
- Delays in notifying stakeholders and executing actions.

### Actions for Investigation

1. Check the network connectivity to the Mistral Notifier pods.
2. Verify the status and logs of Mistral Notifier pods.

### Recommended Actions to Resolve Issue

1. Investigate and resolve network issues if detected.
2. Restart or redeploy Mistral Notifier pods if necessary.
---

## MistralNotifierOverloaded

### Description

Mistral Notifier overloaded, there are lots of unprocessed RPC messages.

### Possible Causes

- High workload causing a backlog of RPC messages.
- Inefficient handling of RPC messages in Mistral Notifier.

### Impact

- Delays in event processing and notification delivery.
- Potential backlog of unprocessed events.

### Actions for Investigation

1. Monitor the rate of incoming RPC messages to Mistral Notifier.
2. Review Mistral Notifier logs for errors related to RPC message processing.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Notifier pods to handle increased workload if necessary.
---

## MistralNotifierCPULoad

### Description

Mistral Notifier uses 90% of the CPU limit.

### Possible Causes

- Inadequate CPU resources allocated to Mistral Notifier pods.
- The service is overloaded.

### Impact

- Increased response time for notifications and event processing.
- Potential delays in notifying stakeholders.

### Actions for Investigation

1. Monitor CPU usage trends in Mistral Notifier pods.
2. Review Mistral Notifier logs for any performance related issues.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Notifier pods if needed.
---

## MistralNotifierMemoryLoad

### Description

Mistral Notifier uses 90% of the memory limit.

### Possible Causes

- Memory leaks or excessive memory consumption by Mistral Notifier.
- Insufficient memory resources allocated to Mistral Notifier pods.

### Impact

- Potential out-of-memory errors and Notifier instability.
- Degraded performance in event notification and handling.

### Actions for Investigation

1. Monitor memory usage trends in Mistral Notifier pods.
2. Review Mistral Notifier logs for memory related errors.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Notifier pods if needed.
2. Investigate and address any memory leaks in the Mistral Notifier code.
---

## MistralMonitoringDegraded

### Description

Mistral Monitoring degraded, there are unavailable Monitoring pods.

### Possible Causes

- Monitoring pod failures or unavailability.
- Resource constraints impacting the Monitoring pod performance.

### Impact

- Reduced or disrupted monitoring and observability capabilities.
- Potential delays in identifying and addressing issues.

### Actions for Investigation

1. Check the status of Mistral Monitoring pods.
2. Review the logs for Mistral Monitoring pods for any errors or issues.
3. Verify resource utilization of the Monitoring pods (CPU, memory).

### Recommended Actions to Resolve Issue

1. Restart or redeploy Mistral Monitoring pods if they are in a failed state.
2. Investigate and address any resource constraints affecting the Monitoring pod performance.
---

## MistralMonitoringDown

### Description

Mistral Monitoring is down, and there are no available Monitoring pods.

### Possible Causes

- Network issues affecting the Monitoring pod communication.
- Mistral Monitoring service or pod failures.

### Impact

- Complete unavailability of Mistral monitoring and observability.
- Potential delays in identifying and addressing issues.

### Actions for Investigation

1. Check the network connectivity to the Mistral Monitoring pods.
2. Verify the status and logs of Mistral Monitoring pods.

### Recommended Actions to Resolve Issue

1. Investigate and resolve network issues if detected.
2. Restart or redeploy Mistral Monitoring pods if necessary.
---

## MistralMonitoringCPULoad

### Description

Mistral Monitoring uses 90% of the CPU limit.

### Possible Causes

- Inadequate CPU resources allocated to Mistral Monitoring pods.
- The service is overloaded.

### Impact

- Potential delays in data collection and monitoring.
- Increased response time for monitoring queries.

### Actions for Investigation

1. Monitor CPU usage trends in Mistral Monitoring pods.
2. Review Mistral Monitoring logs for any performance related issues.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Monitoring pods if needed.
---

## MistralMonitoringMemoryLoad

### Description

Mistral Monitoring uses 90% of the memory limit.

### Possible Causes

- Memory leaks or excessive memory consumption by Mistral Monitoring.
- Insufficient memory resources allocated to Mistral Monitoring pods.

### Impact

- Potential out-of-memory errors and Monitoring instability.
- Degraded performance in data collection and monitoring.

### Actions for Investigation

1. Monitor memory usage trends in Mistral Monitoring pods.
2. Review Mistral Monitoring logs for memory related errors.

### Recommended Actions to Resolve Issue

1. Scale up Mistral Monitoring pods if needed.
2. Investigate and address any memory leaks in the Mistral Monitoring code.
---

## RabbitMQDown

### Description

RabbitMQ is down.

### Possible Causes

- RabbitMQ service failure.
- Network issues affecting the RabbitMQ communication.

### Impact

- Disruption in message queuing and communication.
- Potential impact on various services relying on RabbitMQ.

### Actions for Investigation

1. Check the RabbitMQ service status.
2. Investigate the network connectivity to RabbitMQ.

### Recommended Actions to Resolve Issue

1. Restart RabbitMQ service if necessary.
2. Address network issues affecting the RabbitMQ communication.
---
