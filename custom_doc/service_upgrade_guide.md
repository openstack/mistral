This section covers the upgrade process for the Mistral service.

* [Prerequisites](#prerequisites)
* [Input Parameters](#input-parameters)
* [Upgrade Process](#upgrade-process)
* [Validation Procedures](#validation-procedures)
* [Rollback Strategy](#rollback-strategy)
* [Troubleshooting](#troubleshooting)

# Prerequisites

The following prerequisites should be met:

* Make sure that the Mistral service is running healthy. If there are some problems with Mistral pods, or if Mistral cannot 
serve incoming requests, you must determine the reason and fix it before upgrading.
* RabbitMQ service is up and running.
* PostgreSQL service is up and running.

# Input Parameters

There are several ways to obtain the input parameters for upgrade:

## Obtaining from Previous Upgrade (Installation)

You can find the necessary parameters in the **CUSTOM_PARAMS** field of the corresponding deployer job run.

## Obtaining from Environment
      
Some substantial parameters may be found in the Openshift project resources:

* `mistral-common-params` - Config Map (Your Openshift project -> Resources -> Config Maps).
* `custom-mistral.conf` - Config Map. 

<!-- #GFCFilterMarkerStart# -->
See [Mistral Configuration Parameters Customization](/custom_doc/user.md#mistral-configuration-parameters-customization) for a description of how to specify this map's contents in deployer job params.
<!-- #GFCFilterMarkerEnd# --> 
* `mistral-secret` - Secret, if you have an administrative access to the OpenShift project (Your OpenShift project -> Resources -> Secrets).
    
You can find the description of all Mistral installation parameters at [Main deploy parameters](/custom_doc/installation.md#main-deploy-parameters).

The minimal set of required parameters is described, at [Minimal set of parameters](/custom_doc/installation.md#minimal-set-of-parameters).

# Upgrade Process

A detailed description of the Mistral upgrade/installation process steps can be found in the "Installation Process" section under [Workflow Service Installation Procedure](/custom_doc/installation.md#installation-process).

The only upgrade strategy implemented for Mistral is rolling upgrade. This means that Mistral takes no downtime during upgrade.
Data migration is performed automatically by installation scripts.
	
To upgrade Mistral in your OpenShift project, perform the following steps:

1. Open the deployer job, and click `Build with parameters`.
1. Specify the job parameters. Mistral input parameters must be specified in the **CUSTOM_PARAMS** field.
1. Start the job.

Assumptions and limitations:

* Downgrade (installation of version which is older than the installed one) is not supported.
* Upgrade Pike (5.x.x) version to Train (9.x.x) only available from 5.2.0_nc15+ version. If your version is lower, you should upgrade your Pike version before upgrading to Train.
* Some actions may fail during upgrade. If the corresponding task has no `retry` policy, its execution may fail too.

# Validation Procedures

To make sure that Mistral has been upgraded successfully, check the following:

* Check that all Mistral pods are up and running.
* Check that `<mistral_url>/v2` URL opens with no errors.
* Run _mistral_test_ CI job with `VALIDATE` option enabled to perform automatic Mistral tests.
* If you have an administrative access to the OpenShift project, run these commands from the _mistral-api_ pod terminal:

    ```
    $ source ./envs.sh
    $ mistral run-action std.noop
    ```
    
    It should return an empty result:
    
    ```
    {"result": null}
    ```

# Rollback Strategy

Mistral does not support rollback after an unsuccessful upgrade. In the event of any error, you have to fix its root cause and run the upgrade again.  

# Troubleshooting

There are no known issues with upgrading for now.

In the event of an unsuccessful upgrade, you should collect the `mistral-update-db-***` pod logs. This pod exists only during upgrade or installation, and are deleted several minutes after failure or successful execution. 
Without its logs, it may be quite difficult to find out the reason(s) behind upgrade failure.  
