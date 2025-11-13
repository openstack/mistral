This chapter describes an overview of the Mistral Operator service and its various supported deployment schemes.

<!-- #GFCFilterMarkerStart# -->
[[_TOC_]]
<!-- #GFCFilterMarkerEnd# -->

# Overview

Mistral is a task management service. We can also call it as Workflow Service. Most business processes consist of multiple distinct interconnected steps that need to be executed in a particular order. One can describe such process as a set of tasks and task relations, and upload such descriptions to Mistral so that it takes care of state management, correct execution order, task distribution, and high availability. Mistral calls such a set of tasks and dependencies between them as a workflow. Independent routes are called flows and Mistral can execute them in parallel.

A user can use Mistral to schedule tasks to run within a cloud. Tasks can be anything from executing local processes (shell scripts, binaries) on specified virtual instances to calling REST APIs accessible in a cloud environment. They can also be tasks related to cloud management like creating or terminating virtual instances. It is important that several tasks can be combined in a single workflow and run in a scheduled manner, for example, on Sundays at 2:00 am. Mistral takes care of their parallel execution (if it is logically possible) and fault tolerance, and provides workflow execution management/monitoring capabilities such as stop, resume, current status, errors, and other statistics.

## Terminology

A few basic concepts that one has to understand before going through the Mistral architecture are:

* Workflow - It consists of tasks (at least one) describing what exact steps should be made during a workflow execution.
* Task - It is an activity executed within a workflow definition. Each task has either an Action or a nested Workflow.
* Action - It is the work done when an exact task is triggered.

The following image illustrates an example of Workflow.

![Workflow Example](/docs/public/images/workflow.png)

## Structure

Mistral consists of 5 base components:

* API
* Engine
* Executor
* Notifier
* Monitoring

To communicate between these instances, Mistral uses RabbitMQ, or in some cases Kafka, as an RPC transport channel. To store the data, Mistral uses PostgreSQL.

A high-level scheme of the Mistral application is presented in the following image:

![Application Overview](/docs/public/images/mistral_architecture.png)

The Mistral deployment also includes the following components:

* Operator
* Update DB job

The following sections describe each of these components.

## Mistral API

The API server exposes a REST API to operate and monitor the workflow executions. It works with a database in the read-only format. For create/update/delete requests, it sends a request to Mistral Engine.

## Mistral Engine

The engine picks up the workflows from the API. It handles the control and dataflow of workflow executions. It also computes which tasks are ready and places them in a task queue. It passes the data from task to task, deals with condition transitions, and so on.
The engine works with database read-write permissions.

## Mistral Executor

Mistral Executor executes the actions. It picks up actions from the queue, runs them, and sends the results back to the engine.
Mistral Executor does not have access to the database.

## Mistral Notifier

Mistral Notifier is responsible for sending event notifications. Mistral Engine sends event notifications to a Notifier queue, then the Notifier sends notifications to consumers through HTTP.
Mistral Notifier does not have access to the database.

## Mistral Monitoring

Mistral Monitoring provides an API to get Mistral metrics in the Prometheus format. It also checks for the broken or lost data in the Mistral database and tries to recover it.

## Mistral Operator

The main concept of operators is to extend the Kubernetes (K8s) API by creating the custom resources and controllers that watch this resource.

For more information, refer to the *Official Kubernetes Documentation* at [https://kubernetes.io/docs/concepts/extend-kubernetes/operator/](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/).

This operator is created using Kubernetes Operator Framework. For more information, refer to the *KOPF Documentation* at [https://kopf.readthedocs.io/en/stable/](https://kopf.readthedocs.io/en/stable/).

## Mistral Update DB Job

This job is run during the Mistral deployment. It initializes or upgrades the Mistral database, and prepares everything in the messaging broker.

# Supported Deployment Schemes

The supported deployment schemes are described below.

## On-Prem

### HA Deployment Scheme

The HA deployment scheme is shown below.

![HA Deployment Scheme](/docs/public/images/ha_scheme.png)

From the above image, the main features of the Mistral K8s HA deployment are as follows:

* Mistral does not store any data. To ensure everything is safe, use the database and messaging broker deployed at HA configuration.
* Mistral should have at least 2 instances of each component spread over different nodes.
* As Operator is not a part of the workflow service, there is no need to scale it up.

**Note**: To use Mistral in the non-HA scheme, use only 1 instance of each component.

### DR Deployment Scheme

The HA deployment scheme is shown below.

![DR Deployment Scheme](/docs/public/images/dr_scheme.png)

From the above image, the main features of the Mistral K8s DR deployment are as follows:

* Mistral Operator is presented on both sites.
* On the active site, all Mistral components are scaled up. On the standby site, everything is scaled to 0.
* It is important to use DR proxies for the database and messaging broker for them to be available on both sites without changing the configuration.
