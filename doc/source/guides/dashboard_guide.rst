====================================
Mistral Dashboard Installation Guide
====================================

Mistral dashboard is the plugin for Horizon where it is easily possible to control
mistral objects by interacting with web user interface.

Setup Instructions
------------------
This instruction assumes that Horizon is already installed and it's installation
folder is <horizon>. Detailed information on how to install Horizon can be
found at `Horizon Installation <http://docs.openstack.org/developer/horizon/quickstart.html#setup.>`_

The installation folder of Mistral Dashboard will be referred to as <mistral-dashboard>.

The following should get you started:

1. Clone the repository into your local OpenStack directory::

    $ git clone https://github.com/openstack/mistral-dashboard.git

2. Install mistral-dashboard::

    $ sudo pip install -e <mistral-dashboard>

 Or if you're planning to run Horizon server in a virtual environment (see below)::

    $ tox -evenv -- pip install -e ../mistral-dashboard/

 and then::

    $ cp -b <mistral-dashboard>/_50_mistral.py.example <horizon>/openstack_dashboard/local/enabled/_50_mistral.py

3. Since Mistral only supports Identity v3, you must ensure that the dashboard points the proper OPENSTACK_KEYSTONE_URL in <horizon>/openstack_dashboard/local/local_settings.py file::

    OPENSTACK_API_VERSIONS = {
        "identity": 3,
    }

    OPENSTACK_KEYSTONE_URL = "http://%s:5000/v3" % OPENSTACK_HOST

4. Also, make sure you have changed OPENSTACK_HOST to point to your Keystone server and check all endpoints are accessible. You may want to change OPENSTACK_ENDPOINT_TYPE to "publicURL" if some of them are not.

5. When you're ready, you would need to either restart your apache::

    $ sudo service apache2 restart

 or run the development server (in case you have decided to use local horizon)::

    $ cd ../horizon/
    $ tox -evenv -- python manage.py runserver

Debug Instructions
------------------
Please refer to :doc:`Mistral Troubleshooting <../developer/troubleshooting>`