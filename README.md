# Mistral

Workflow Service is integrated with OpenStack. This project aims to provide a
mechanism to define tasks and workflows in a simple YAML-based language, manage
and execute them in a distributed environment.

[**Mistral Operator Repository**](https://github.com/Netcracker/qubership-mistral-operator/) - Some general information is located in this repository.

<!-- #GFCFilterMarkerStart# -->
[[_TOC_]]
<!-- #GFCFilterMarkerEnd# -->

## Repository Structure

The repository stucture is described below.

- `./config` - contains config template and some scripts for building the component
- `./custom_doc` - internal documentation
- `./doc` - opensource docs
- `./mistral` - contains Mistral's source code 
- `./operator` - contains source code and build for mistral operator 
- `./playbooks` - ansible playbooks
- `./rally-jobs` - this directory contains rally tasks and plugins that are run by OpenStack CI
- `./tests` - directory with junit and robot tests
-  `./tools` - some tools

## How to Start

Refer to the Mistral Operator's [Guide](/operator/README.md)

### How to Debug

To debug Mistral in VSCode, you can use `Mistral[ALL]` configuration which is already defined in the `.vscode/launch.json` file.

## Useful Links

Some useful links are listed below.

* [Mistral Official Documentation](https://docs.openstack.org/mistral/latest/)

    * [User Documentation](https://docs.openstack.org/mistral/latest/user/index.html)

    * [Administrator Documentation](https://docs.openstack.org/mistral/latest/admin/index.html)

    * [Developer Documentation](https://docs.openstack.org/mistral/latest/developer/index.html)

* Project status, bugs, and blueprints are tracked on
  [Launchpad](https://launchpad.net/mistral/)

* CloudFlow: Visualization tool for workflow executions on https://github.com/nokia/CloudFlow

* Apache License Version 2.0 http://www.apache.org/licenses/LICENSE-2.0

* Release notes for the project can be found at:
  https://docs.openstack.org/releasenotes/mistral/

* Source for the project can be found at:
  https://opendev.org/openstack/mistral

* WSGI app is located in `mistral/api/wsgi.py`

* Mistral Operator https://github.com/Netcracker/qubership-mistral-operator/
* [Installation guide](/custom_doc/installation.md)
* [Troubleshooting guide](/custom_doc/troubleshooting.md)
* [Dev Guide](/custom_doc/dev.md)
