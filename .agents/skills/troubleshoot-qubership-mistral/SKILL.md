---
name: troubleshoot-qubership-mistral
description: Diagnose Qubership Mistral deployment and runtime failures — error-status workflows, stuck executions, unresponsive API, RabbitMQ/DB issues, monitoring alarms. Use when triaging a broken Mistral deployment or reading its alarms/logs.
---

# Troubleshooting Qubership Mistral

`references/troubleshooting.md` is the fact source for known failure
modes: symptom → problem → solution, one `#`-level section per issue.
It's ~300 lines and growing — don't read it in full for a single
symptom.

## Reading the reference file

1. Grep headers with line numbers first:
   `grep -n '^#' references/troubleshooting.md`
2. Match the symptom at hand against the jump table below (or the raw
   headers if the table is stale) to pick the section.
3. Read only that section: offset at its line number, limit through to
   the next header's line number. Never load the whole file for one
   lookup.

## Symptom → reference section

| Symptom                                                                              | Header in references/troubleshooting.md                   |
|--------------------------------------------------------------------------------------|-----------------------------------------------------------|
| Workflow has "error" status                                                          | Mistral Workflow has Error Status                         |
| API not responding / slow                                                            | Mistral API is Not Responding                             |
| Execution of workflow is stuck                                                       | Execution of Workflow is Stuck                            |
| Service failed to deploy                                                             | Mistral Service was not Deployed                          |
| Execution/action creation request hangs or times out                                 | Request on Execution Creation is Stuck                    |
| Entities invisible across requests / `DBEntityNotFoundError`                         | Different IDP Tenants                                     |
| RabbitMQ backlog growing / service OOM on reconnect                                  | RabbitMQ Collects a Lot of Messages                       |
| Deploy with `clean` flag fails (active DB connections)                               | Mistral Cannot Deploy Because of Active Connections to DB |
| Need to purge or trim execution history                                              | How to Clean Mistral Database                             |
| Monitoring alarm firing (Down/Degraded/CPULoad/MemoryLoad/RabbitMQ connections down) | Monitoring Alarms Description                             |

## Beyond the reference file

For a stuck execution, the reference file only says to check Engine/
Executor logs for OOM and recent redeploys. It doesn't mention: the
recovery jobs in `mistral/monitoring/jobs/` (delayed calls, idle tasks,
waiting tasks, subworkflow start/complete) are what should reclaim a
stalled execution automatically. If it's still stuck after a recovery
cycle, check those jobs are actually running before digging further.
