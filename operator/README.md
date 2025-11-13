<!-- #GFCFilterMarkerStart# -->
[[_TOC_]]
<!-- #GFCFilterMarkerEnd# -->

## Repository Structure

The repository stucture is described below.

* `./bluegreen-agent` - bg agent from migrating workflows during bg deployment
* `./build` - directory contains scripts for building docker image
* `./delete-dvm-deploy-artifacts` - contains script for cleanup cleaning up Mistral's resources
* `./deploy` - description
* `./deployments` - directory with HELM charts for the Mistral
* `./docs` - directory with actual documentation for the service.
* `./src` - directory with operator source code, which is used for running the Mistral

## How to Start

The following sub-sections provide the detailed instructions.

### Build

### Deploy to k8s

#### Pure Helm

Refer to the [**Helm guide**](docs/public/installation.md#helm).

### How to Debug

Refer to the Mistral's [Guide](https://github.com/Netcracker/qubership-mistral/-/blob/master_qs/README.md).

### How to Troubleshoot
There are no well-defined rules for troubleshooting, as each task is unique, but there are some tips that can do:
* Deploy parameters.
* Application manifest.
* Logs from all Mistral services. Mostly all problems will be in *engine* service logs, but others should be checked too. 
* As Mistral depends on Postgres, RabbitMQ and partly on Kafka, there can be connection problems

Also, developer can take a look on [Troubleshooting guide](/docs/public/troubleshooting.md).
   
## Useful links

* Mistral https://github.com/Netcracker/qubership-mistral
* [Installation guide](/docs/public/installation.md)
* [Troubleshooting guide](/docs/public/troubleshooting.md)
* [Architecture Guide](/docs/public/architecture.md)