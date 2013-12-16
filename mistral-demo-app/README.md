Mistral Demo app
================

This mini-project demonstrates basic Mistral capabilities.


### Installation
First of all, in a shell run:

*tox*

This will install necessary virtual environments and run all the project tests. Installing virtual environments may take significant time (~10-15 mins).

Then make a sym-link to mistralclient package

*cd mistral-demo-app*
*ln -s <full-path-to-mistralclient> mistralclient

### Running Mistral Demo app server
To run Mistral Demo app server perform the following commands in a shell:

*tox -evenv -- python demo_app/cmd/main.py*

Then it will automatically upload necessary workbook and run workflow.
