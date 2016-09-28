# Copyright 2014 - Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import mock

from mistral.actions.openstack import actions
from mistral import config
from mistral import context as ctx
from oslotest import base


class FakeEndpoint(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class OpenStackActionTest(base.BaseTestCase):
    @mock.patch.object(actions.NovaAction, '_get_client')
    def test_nova_action(self, mocked):
        method_name = "servers.get"
        action_class = actions.NovaAction
        action_class.client_method_name = method_name
        params = {'server': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().servers.get.called)
        mocked().servers.get.assert_called_once_with(server="1234-abcd")

    @mock.patch('mistral.actions.openstack.actions.keystone_utils.get_'
                'keystone_endpoint_v2')
    @mock.patch('mistral.actions.openstack.actions.keystone_utils.get_'
                'endpoint_for_project')
    @mock.patch('mistral.actions.openstack.actions.novaclient')
    def test_nova_action_config_endpoint(self, mock_novaclient,
                                         mock_nova_endpoint,
                                         mock_ks_endpoint_v2):

        # this is the default, but be explicit
        config.CONF.set_default('os_actions_endpoint_type', 'public')

        test_ctx = ctx.MistralContext(
            user_id=None,
            project_id='1234',
            project_name='admin',
            auth_token=None,
            is_admin=False,
            # set year to 3016 in order for token to always be valid
            expires_at='3016-07-13T18:34:22.000000Z'
        )
        ctx.set_ctx(test_ctx)

        # attributes mirror keystone Endpoint object exactly
        # (with endpoint type public)
        keystone_attrs = {
            'url': 'http://192.0.2.1:5000/v2.0',
            'enabled': True,
            'id': 'b1ddf133fa6e491c8ee13701be97db2d',
            'interface': 'public',
            'links': {
                u'self': u'http://192.0.2.1:5000/v3/endpoints/'
                'b1ddf133fa6e491c8ee13701be97db2d'
            },
            'region': 'regionOne',
            'region_id': 'regionOne',
            'service_id': '8f4afc75cd584d5cb381f68a9db80147',
        }
        keystone_endpoint = FakeEndpoint(**keystone_attrs)

        nova_attrs = {
            'url': 'http://192.0.2.1:8774/v2/%(tenant_id)s',
            'enabled': True,
            'id': '5bb51b33c9984513b52b6a3e85154305',
            'interface': 'public',
            'links': {
                u'self': u'http://192.0.2.1:5000/v3/endpoints/'
                '5bb51b33c9984513b52b6a3e85154305'
            },
            'region': 'regionOne',
            'region_id': 'regionOne',
            'service_id': '1af46173f37848edb65bd4962ed2d09d',
        }
        nova_endpoint = FakeEndpoint(**nova_attrs)

        mock_ks_endpoint_v2.return_value(keystone_endpoint)
        mock_nova_endpoint.return_value(nova_endpoint)

        method_name = "servers.get"
        action_class = actions.NovaAction
        action_class.client_method_name = method_name
        params = {'server': '1234-abcd'}
        action = action_class(**params)
        action.run()

        mock_novaclient.Client.assert_called_once_with(
            2,
            username=None,
            api_key=None,
            endpoint_type='public',
            service_type='compute',
            auth_token=test_ctx.auth_token,
            tenant_id=test_ctx.project_id,
            region_name=mock_ks_endpoint_v2().region,
            auth_url=mock_ks_endpoint_v2().url
        )

        self.assertTrue(mock_novaclient.Client().servers.get.called)
        mock_novaclient.Client().servers.get.assert_called_once_with(
            server="1234-abcd")

        # Repeat test in order to validate cache.
        mock_novaclient.reset_mock()
        action.run()

        # TODO(d0ugal): Uncomment the following line when caching is fixed.
        # mock_novaclient.Client.assert_not_called()
        mock_novaclient.Client().servers.get.assert_called_with(
            server="1234-abcd")

        # Repeat again with different context for cache testing.
        test_ctx.project_name = 'service'
        test_ctx.project_id = '1235'
        ctx.set_ctx(test_ctx)

        mock_novaclient.reset_mock()
        action.run()
        mock_novaclient.Client.assert_called_once_with(
            2,
            username=None,
            api_key=None,
            endpoint_type='public',
            service_type='compute',
            auth_token=test_ctx.auth_token,
            tenant_id=test_ctx.project_id,
            region_name=mock_ks_endpoint_v2().region,
            auth_url=mock_ks_endpoint_v2().url
        )

        self.assertTrue(mock_novaclient.Client().servers.get.called)
        mock_novaclient.Client().servers.get.assert_called_once_with(
            server="1234-abcd")

    @mock.patch.object(actions.GlanceAction, '_get_client')
    def test_glance_action(self, mocked):
        method_name = "images.delete"
        action_class = actions.GlanceAction
        action_class.client_method_name = method_name
        params = {'image': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().images.delete.called)
        mocked().images.delete.assert_called_once_with(image="1234-abcd")

    @mock.patch.object(actions.KeystoneAction, '_get_client')
    def test_keystone_action(self, mocked):
        method_name = "users.get"
        action_class = actions.KeystoneAction
        action_class.client_method_name = method_name
        params = {'user': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().users.get.called)
        mocked().users.get.assert_called_once_with(user="1234-abcd")

    @mock.patch.object(actions.HeatAction, '_get_client')
    def test_heat_action(self, mocked):
        method_name = "stacks.get"
        action_class = actions.HeatAction
        action_class.client_method_name = method_name
        params = {'id': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().stacks.get.called)
        mocked().stacks.get.assert_called_once_with(id="1234-abcd")

    @mock.patch.object(actions.NeutronAction, '_get_client')
    def test_neutron_action(self, mocked):
        method_name = "show_network"
        action_class = actions.NeutronAction
        action_class.client_method_name = method_name
        params = {'id': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().show_network.called)
        mocked().show_network.assert_called_once_with(id="1234-abcd")

    @mock.patch.object(actions.CinderAction, '_get_client')
    def test_cinder_action(self, mocked):
        method_name = "volumes.get"
        action_class = actions.CinderAction
        action_class.client_method_name = method_name
        params = {'volume': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().volumes.get.called)
        mocked().volumes.get.assert_called_once_with(volume="1234-abcd")

    @mock.patch.object(actions.CeilometerAction, '_get_client')
    def test_ceilometer_action(self, mocked):
        method_name = "alarms.get"
        action_class = actions.CeilometerAction
        action_class.client_method_name = method_name
        params = {'alarm_id': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().alarms.get.called)
        mocked().alarms.get.assert_called_once_with(alarm_id="1234-abcd")

    @mock.patch.object(actions.TroveAction, '_get_client')
    def test_trove_action(self, mocked):
        method_name = "instances.get"
        action_class = actions.TroveAction
        action_class.client_method_name = method_name
        params = {'instance': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().instances.get.called)
        mocked().instances.get.assert_called_once_with(instance="1234-abcd")

    @mock.patch.object(actions.IronicAction, '_get_client')
    def test_ironic_action(self, mocked):
        method_name = "node.get"
        action_class = actions.IronicAction
        action_class.client_method_name = method_name
        params = {'node': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().node.get.called)
        mocked().node.get.assert_called_once_with(node="1234-abcd")

    @mock.patch.object(actions.BaremetalIntrospectionAction, '_get_client')
    def test_baremetal_introspector_action(self, mocked):
        method_name = "get_status"
        action_class = actions.BaremetalIntrospectionAction
        action_class.client_method_name = method_name
        params = {'uuid': '1234'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().get_status.called)
        mocked().get_status.assert_called_once_with(uuid="1234")

    @mock.patch.object(actions.MistralAction, '_get_client')
    def test_mistral_action(self, mocked):
        method_name = "workflows.get"
        action_class = actions.MistralAction
        action_class.client_method_name = method_name
        params = {'name': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().workflows.get.called)
        mocked().workflows.get.assert_called_once_with(name="1234-abcd")

    @mock.patch.object(actions.SwiftAction, '_get_client')
    def test_swift_action(self, mocked):
        method_name = "get_object"
        action_class = actions.SwiftAction
        action_class.client_method_name = method_name
        params = {'container': 'foo', 'object': 'bar'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().get_object.called)
        mocked().get_object.assert_called_once_with(container='foo',
                                                    object='bar')

    @mock.patch.object(actions.ZaqarAction, '_get_client')
    def test_zaqar_action(self, mocked):
        method_name = "queue_messages"
        action_class = actions.ZaqarAction
        action_class.client_method_name = method_name
        params = {'queue_name': 'foo'}
        action = action_class(**params)
        action.run()

        mocked().queue.assert_called_once_with('foo')
        mocked().queue().messages.assert_called_once_with()

    @mock.patch.object(actions.BarbicanAction, '_get_client')
    def test_barbican_action(self, mocked):
        method_name = "orders_list"
        action_class = actions.BarbicanAction
        action_class.client_method_name = method_name
        params = {'limit': 5}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().orders_list.called)
        mocked().orders_list.assert_called_once_with(limit=5)

    @mock.patch.object(actions.DesignateAction, '_get_client')
    def test_designate_action(self, mocked):
        method_name = "domain.get"
        action_class = actions.DesignateAction
        action_class.client_method_name = method_name
        params = {'domain': 'example.com'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().domain.get.called)
        mocked().domain.get.assert_called_once_with(domain="example.com")

    @mock.patch.object(actions.MagnumAction, '_get_client')
    def test_magnum_action(self, mocked):
        method_name = "baymodels.get"
        action_class = actions.MagnumAction
        action_class.client_method_name = method_name
        params = {'id': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().baymodels.get.called)
        mocked().baymodels.get.assert_called_once_with(id="1234-abcd")

    @mock.patch.object(actions.MuranoAction, '_get_client')
    def test_murano_action(self, mocked):
        method_name = "categories.get"
        action_class = actions.MuranoAction
        action_class.client_method_name = method_name
        params = {'category_id': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().categories.get.called)
        mocked().categories.get.assert_called_once_with(
            category_id="1234-abcd"
        )

    @mock.patch.object(actions.TackerAction, '_get_client')
    def test_tacker_action(self, mocked):
        method_name = "show_vim"
        action_class = actions.TackerAction
        action_class.client_method_name = method_name
        params = {'vim_id': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().show_vim.called)
        mocked().show_vim.assert_called_once_with(
            vim_id="1234-abcd"
        )
