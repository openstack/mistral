## Mistral API failed to response

The problem of Mistral API failing to response is described below.

### Description

When trying to get workflow execution, mistral API returns an empty request.

### Alerts

- MistralAPICPULoad
- MistralAPIMemoryLoad

### Stack Trace(s)

```text
curl returns Empty reply from server
```
### How to solve

Increase CPU and Memory for Mistral API.

### Recommendations

The recommendations are as follows:

1. Monitor the CPU usage trends in Mistral API pods.
2. Review Mistral API logs for any performance related issues.

## Mistral Service Degraded

The problem of Mistral service degraded is described below.

### Description
Some of Mistral Services degraded, there are unavailable pods.

### Alerts
- MistralAPIDegraded
- MistralEngineDegraded
- MistralExecutorDegraded
- MistralNotifierDegraded
- MistralMonitoringDegraded

### Stack trace(s)
```text
Not applicable
```

### How to solve
1. **Check the status of Mistral Service pods:**
   - Use `kubectl get pods` to see if any pods are in a failed state.
2. **Review logs for the Mistral Service pods:**
   - Use `kubectl logs <pod-name>` to examine logs for errors.
3. **Verify resource utilization:**
   - Check CPU and memory usage with `kubectl top pod`.

### Recommendations
Not applicable

## Mistral Service Down

The problem of Mistral service down is described below.

### Description

Some of Mistral Services are down, and there are no available pods.

### Alerts
- MistralAPIDown
- MistralEngineDown
- MistralExecutorDown
- MistralNotifierDown
- MistralMonitoringDown


### Stack trace(s)
```text
Not applicable
```

### How to solve

1. **Check the network connectivity to the Mistral Service pods:**
   - Verify network routes and DNS resolution.
2. **Verify the status and logs of Mistral Service pods:**
   - Use `kubectl logs <pod-name>` to review logs.
   - Check pod status using `kubectl get pods`.

### Recommendations
Not applicable

## Mistral Service's CPU Loaded

The problem of Mistral service's CPU loaded is described below.

### Description

Mistral Service uses 90% of the CPU limit.

### Alerts
- MistralAPICPULoad
- MistralEngineCPULoad
- MistralExecutorCPULoad
- MistralNotifierCPULoad
- MistralMonitoringCPULoad

### Stack trace(s)
```text
Not applicable
```

### How to solve

1. **Monitor CPU usage trends in Mistral Service pods:**
   - Use `kubectl top pod` to review CPU utilization.
2. **Review Mistral Service's logs for any performance-related issues:**
   - Check logs with `kubectl logs <pod-name>` for any anomalies.

### Recommendations

The recommendations are as follows:

- Scale up Mistral Service's pods, if needed.
- Consider optimizing the workload or adjusting resource limits.

## Mistral Service's Memory Loaded

The problem of Mistral service's memory loaded is described below.

### Description

Mistral Service uses 90% of the memory limit.

### Alerts
- MistralAPIMemoryLoad
- MistralEngineMemoryLoad
- MistralExecutorMemoryLoad
- MistralNotifierMemoryLoad
- MistralMonitoringMemoryLoad

### Stack trace(s)
```text
Not applicable
```

### How to solve
1. **Monitor memory usage trends in Mistral Service pods:**
   - Use `kubectl top pod` to monitor memory usage.
2. **Review Mistral Service logs for memory-related errors:**
   - Check logs using `kubectl logs <pod-name>`.

### Recommendations

The recommendations are as follows:

- Scale up Mistral Service pods, if needed.
- Investigate and address any memory leaks in the Mistral Service code to prevent recurrence.
