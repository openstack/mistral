This section describes Mistral dashboard and their metrics.
# Labels

This dashboard has the `mistral` label.

# Metrics

This section describes metrics and their meanings.

## Overview

An overview of the Mistral dashboard is given below.

![Overview](/custom_doc/img/grafana_overview.PNG)

* `Mistral Cluster Status` - Displays the Mistral cluster status such as Running, Degraded, Down.
* `Maintenance status` - Displays the Mistral maintenance mode status.
* `Completion speed per sec` - Displays the number of completed workflows, tasks, and actions per second.
* `CPU Usage Summary` - Displays the amount of millicores requested by Mistral pods, millicore usage, and limit.
* `Mistral E2E Smoke` - Displays the Mistral E2E smoke test status.
* `Tasks in non-terminal state` - Displays the number of tasks in non-terminal state.
* `MEM Usage Summary` - Displays the amount of memory requested by Mistral pods, memory usage, and limit.

## Mistral Apps Status

The Mistral applications statuses are displayed as follows:

![Mistral Apps Status](/custom_doc/img/mistral_apps_status.PNG)

* `Mistral API Status` - Displays the Mistral API status such as Running, Degraded, Down.
* `Mistral Executor Status` - Displays the Mistral executor status such as Running, Degraded, Down.
* `Mistral Engine Status` - Displays the Mistral engine status such as Running, Degraded, Down.
* `Mistral Notifier Status` - Displays the Mistral notifier status such as Running, Degraded, Down.
* `Mistral Monitoring Status` - Displays the Mistral monitoring status such as Running, Degraded, Down.
* `Mistral API pods` - Displays the current number of available Mistral API pods.
* `Mistral Executor pods` - Displays the current number of available Mistral Executor pods.
* `Mistral Engine pods` - Displays the current number of available Mistral Engine pods.
* `Mistral Notifier pods` - Displays the current number of available Mistral Notifier pods.
* `Mistral Monitoring pods` - Displays the current number of available Mistral Monitoring pods.

## Total Mistral Entities

The total Mistral entities are displayed as follows:

![Total Mistral Entities](/custom_doc/img/grafana_total_mistral_entities.PNG)

* `Workflow count by state` - Displays the workflows count by state.
* `Task count by state` - Displays the tasks count by state.
* `Delayed calls count by target` - Displays the delayed calls count by target.
* `Action count by state` - Displays the actions count by state.

## Mistral CPU Usage

The Mistral CPU usage information is displayed as follows:

![Mistral CPU Usage](/custom_doc/img/grafana_mistral_cpu_usage.PNG)

* `Mistral Engine CPU Usage` - Displays the Mistral Engine CPU usage in millicores, CPU limit, and CPU requested for each engine pod.
* `Mistral API CPU Usage` - Displays the Mistral API CPU usage in millicores, CPU limit, and CPU requested for each API pod.
* `Mistral Executor CPU Usage` - Displays the Mistral Executor CPU usage in millicores, CPU limit, and CPU requested for each Executor pod.
* `Mistral Notifier CPU Usage` - Displays the Mistral Notifier CPU usage in millicores, CPU limit, and CPU requested for each Notifier pod.
* `Mistral Monitoring CPU Usage` - Displays the Mistral Monitoring CPU usage in millicores, CPU limit, and CPU requested for each Monitoring pod.

## Mistral MEM Usage

The Mistral MEM usage information is displayed as follows:

![Mistral MEM Usage](/custom_doc/img/grafana_mistral_mem_usage.PNG)

* `Mistral Engine MEM Usage` - Displays the Mistral Engine memory usage in MiB, memory limit, and memory requested for each Engine pod.
* `Mistral Executor MEM Usage` - Displays the Mistral Executor memory usage in MiB, memory limit, and memory requested for each Executor pod.
* `Mistral API MEM Usage` - Displays the Mistral API memory usage in MiB, memory limit, and memory requested for each API pod.
* `Mistral Notifier MEM Usage` - Displays the Mistral Notifier memory usage in MiB, memory limit, and memory requested for each Notifier pod.
* `Mistral Monitoring MEM Usage` - Displays the Mistral Monitoring memory usage in MiB, memory limit, and memory requested for each Monitoring pod.

## RabbitMQ

The RabbitMQ information is displayed below.

![RabbitMQ](/custom_doc/img/grafana_rabbitmq.PNG)

* `RabbitMQ Status` - Displays the RabbitMQ status (Running, Down).
* `Mistral Engine Messages Count` - Displays the number of messages in Mistral engine queue.
* `Mistral Executor Messages Count` - Displays the number of messages in Mistral executor queue.
* `Mistral Notifier Messages Count` - Displays the number of messages in Mistral notifier queue.
