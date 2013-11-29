Mistral
=======

Task Orchestration and Scheduling service for OpenStack cloud


Running in development mode
---------------------------

### Installation
First of all, in a shell run:

*tox*

This will install necessary virtual environments and run all the project tests. Installing virtual environments may take significant time (~10-15 mins).

### Mistral configuration

Open *etc/mistral.conf* file and fix configuration properties as needed. For example, *host* and *port* specified by default may not be desired in a particular environment.

### Running Mistral API server
To run Mistral API server perform the following commands in a shell:
 
*tox -epy27 -- /mistral/cmd/api.py --config-file etc/mistral.conf*