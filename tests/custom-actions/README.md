# Content

* [Custom Actions](#custom-actions)
* [Develop Custom Actions](#develop-custom-actions)
* [Upload library](#upload-library)

## Custom Actions

You need to create a python library for adding a custom actions.

Create the `setup.py`
```python
import setuptools

try:
    import multiprocessing  # noqa
except ImportError:
    pass

setuptools.setup(
    setup_requires=['pbr>=2.0.0'],
    pbr=True)
```

Add the dependency containing basic Mistral entities and logging 

`
oslo.log
mistral-lib
`

Create the `setup.cfg`
```
[metadata]
name = myaction
summary = Test Custom Mistral Action

[files]
packages =
    myaction

[entry_points]
mistral.actions =
    naruto = myaction.naruto:NarutoSay
```

Create a action

```python
from mistral_lib import actions
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class NarutoSay(actions.Action):
    """This action repeat the famous phrase of Naruto Uzumaki

        :param message: (optional, 'Dattebayo' by default) a phrase for
        Naruto
        """
    def __init__(self, message='Dattebayo'):
        self.message = message

    def run(self, context):
        LOG.info('Naruto says: "{0}"'.format(self.message))
        
        # return your results 
        return self.message
```

Publish the your classes in a `mistral.actions` namespace
in the your `setup.cfg` file.

### Develop Custom Actions

Developing a custom Mistral actions looks like the developing Mistral.
First of all you should to start PostgreSQL and RabbitMQ images.

Than you should overwrite the original Mistral Docker image and add your library to the image.
Add this example to the your custom actions library:
```docker
# It's a Mistral Docker image. You should use the Mistral version 5.1.0 and more.
FROM docker.com:17008/mistral/feature-sync-with-previous-version:3

# An your source of actions will be here
ENV CUSTOM_ACTIONS_SOURCE_FOLDER="/opt/mano9-actions"
# Change to root user to avoid a problems with verivication of the Linux rights
USER root

# Add source of your action to the Mistral image
ADD . "${CUSTOM_ACTIONS_SOURCE_FOLDER}"
# Install the your library with Mistral actions
RUN pip install -e "${CUSTOM_ACTIONS_SOURCE_FOLDER}"
```

Finally start the Mistral container.
The alternative is to start from console:
```
docker build -t custom-actions .
docker run --rm --net=host --entrypoint="sh" -e RABBIT_HOST=localhost -e PG_HOST=localhost -e PG_DB_NAME=mistral_new1 -it --name=custom-actions custom-actions upgrade_db_and_start.sh
```