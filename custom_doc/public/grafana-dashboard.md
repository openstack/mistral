This section describes the Mistral dashboard and their metrics. The Mistral dashboard displays metrics from Prometheus.

# Labels

This dashboard has the `mistral` label.

# Metrics

This section describes metrics and their meanings.

## Overview

An overview of the Mistral dashboard is given below.

![Overview](/docs/public/images/grafana_overview.PNG)

* `Mistral Cluster Status` - Displays the Mistral cluster status (Up, Degraded, Down).
* `Maintenance status` - Displays the Mistral maintenance mode status.
* `Completion speed per sec` - Displays the number of completed workflows, tasks, and actions per second.
* `CPU Usage Summary` - Displays the amount of millicores requested by Mistral pods, millicore usage, and limit.
* `Mistral E2E Smoke` - Displays the Mistral E2E smoke test status.
* `Tasks in non-terminal state` - Displays the number of tasks in non-terminal state.
* `MEM Usage Summary` - Displays the amount of memory requested by Mistral pods, memory usage, and limit.

## Mistral Apps Status

The following images displays the Mistral applications status:

![Mistral Apps Status](/docs/public/images/mistral_apps_status.PNG)

* `Mistral API Status` - Displays the Mistral API status (Up, Degraded, Down).
* `Mistral Executor Status` - Displays the Mistral executor status (Up, Degraded, Down).
* `Mistral Engine Status` - Displays the Mistral engine status (Up, Degraded, Down).
* `Mistral Notifier Status` - Displays the Mistral notifier status (Up, Degraded, Down).
* `Mistral Monitoring Status` - Displays the Mistral monitoring status (Up, Degraded, Down).
* `Mistral API pods` - Displays the current number of available Mistral API pods.
* `Mistral Executor pods` - Displays the current number of available Mistral Executor pods.
* `Mistral Engine pods` - Displays the current number of available Mistral Engine pods.
* `Mistral Notifier pods` - Displays the current number of available Mistral Notifier pods.
* `Mistral Monitoring pods` - Displays the current number of available Mistral Monitoring pods.
* `Mistral pods restart count` – Displays the total number of restarts for each Mistral pod over the selected time range. 
* `Mistral pod restarts by reason` – Shows the reason for the most recent container termination (for example, OOMKilled, Error, or Completed) for each Mistral pod.

## Total Mistral Entities

The following images displays the total Mistral entities:

![Total Mistral Entities](/docs/public/images/grafana_total_mistral_entities.PNG)

* `Workflow count by state` - Displays the workflows count by state.
* `Task count by state` - Displays the tasks count by state.
* `Delayed calls count by target` - Displays the delayed calls count by target.
* `Action count by state` - Displays the actions count by state.
* `Mistral 50 task retries` – Displays how many times the latest 50 Mistral tasks were retried.
* `Latest 50 Workflow Executions` - Displays the 50 most recent workflow executions based on their creation time.

## Mistral CPU Usage

The following images displays the Mistral CPU usage:

![Mistral CPU Usage](/docs/public/images/grafana_mistral_cpu_usage.PNG)

* `Mistral Engine CPU Usage` - Displays the Mistral Engine CPU usage in cores, CPU limit, and CPU requested for each engine pod.
* `Mistral API CPU Usage` - Displays the Mistral API CPU usage in cores, CPU limit, and CPU requested for each API pod.
* `Mistral Executor CPU Usage` - Displays the Mistral Executor CPU usage in cores, CPU limit, and CPU requested for each Executor pod.
* `Mistral Notifier CPU Usage` - Displays the Mistral Notifier CPU usage in cores, CPU limit, and CPU requested for each Notifier pod.
* `Mistral Monitoring CPU Usage` - Displays the Mistral Monitoring CPU usage in cores, CPU limit, and CPU requested for each Monitoring pod.

## Mistral MEM Usage

The following images displays the Mistral MEM usage:

![Mistral MEM Usage](/docs/public/images/grafana_mistral_mem_usage.PNG)

* `Mistral Engine MEM Usage` - Displays the Mistral Engine memory usage in MiB, memory limit, and memory requested for each Engine pod.
* `Mistral Executor MEM Usage` - Displays the Mistral Executor memory usage in MiB, memory limit, and memory requested for each Executor pod.
* `Mistral API MEM Usage` - Displays the Mistral API memory usage in MiB, memory limit, and memory requested for each API pod.
* `Mistral Notifier MEM Usage` - Displays the Mistral Notifier memory usage in MiB, memory limit, and memory requested for each Notifier pod.
* `Mistral Monitoring MEM Usage` - Displays the Mistral Monitoring memory usage in MiB, memory limit, and memory requested for each Monitoring pod.

## RabbitMQ

The following images displays the RabbitMQ details:

![RabbitMQ](/docs/public/images/grafana_rabbitmq.PNG)

* `RabbitMQ Status` - Displays the RabbitMQ status (Up, Down).
* `Mistral Engine Messages Count` - Displays the number of messages in Mistral engine queue.
* `Mistral Executor Messages Count` - Displays the number of messages in Mistral executor queue.
* `Mistral Notifier Messages Count` - Displays the number of messages in Mistral notifier queue.
