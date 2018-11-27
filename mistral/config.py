# Copyright 2013 - Mirantis, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
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

"""
Configuration options registration and useful routines.
"""

import itertools
import json
import os

from keystoneauth1 import loading
from oslo_config import cfg
from oslo_log import log
from oslo_middleware import cors
from osprofiler import opts as profiler

from mistral import version

from mistral._i18n import _

# Options under default group.
launch_opt = cfg.ListOpt(
    'server',
    default=['all'],
    help=_('Specifies which mistral server to start by the launch script. '
           'Valid options are all or any combination of '
           'api, engine, and executor.')
)

wf_trace_log_name_opt = cfg.StrOpt(
    'workflow_trace_log_name',
    default='workflow_trace',
    help=_('Logger name for pretty workflow trace output.')
)

use_debugger_opt = cfg.BoolOpt(
    'use-debugger',
    default=False,
    help=_('Enables debugger. Note that using this option changes how the '
           'eventlet library is used to support async IO. This could result '
           'in failures that do not occur under normal operation. '
           'Use at your own risk.')
)

auth_type_opt = cfg.StrOpt(
    'auth_type',
    default='keystone',
    help=_('Authentication type (valid options: keystone, keycloak-oidc)')
)

api_opts = [
    cfg.HostAddressOpt(
        'host',
        default='0.0.0.0',
        help='Mistral API server host'
    ),
    cfg.PortOpt('port', default=8989, help='Mistral API server port'),
    cfg.BoolOpt(
        'allow_action_execution_deletion',
        default=False,
        help=_('Enables the ability to delete action_execution which '
               'has no relationship with workflows.')
    ),
    cfg.BoolOpt(
        'enable_ssl_api',
        default=False,
        help=_('Enable the integrated stand-alone API to service requests '
               'via HTTPS instead of HTTP.')
    ),
    cfg.IntOpt(
        'api_workers',
        help=_('Number of workers for Mistral API service '
               'default is equal to the number of CPUs available if that can '
               'be determined, else a default worker count of 1 is returned.')
    )
]

js_impl_opt = cfg.StrOpt(
    'js_implementation',
    default='pyv8',
    choices=['pyv8', 'v8eval', 'py_mini_racer'],
    help=_('The JavaScript implementation to be used by the std.javascript '
           'action to evaluate scripts.')
)

rpc_impl_opt = cfg.StrOpt(
    'rpc_implementation',
    default='oslo',
    choices=['oslo', 'kombu'],
    help=_('Specifies RPC implementation for RPC client and server. '
           'Support of kombu driver is experimental.')
)

# TODO(ddeja): This config option is a part of oslo RPCClient
# It would be the best to not register it twice, rather use RPCClient somehow
rpc_response_timeout_opt = cfg.IntOpt(
    'rpc_response_timeout',
    default=60,
    help=_('Seconds to wait for a response from a call.')
)

oslo_rpc_executor = cfg.StrOpt(
    'oslo_rpc_executor',
    default='eventlet',
    choices=['eventlet', 'blocking', 'threading'],
    help=_('Executor type used by Oslo Messaging framework. Defines how '
           'Oslo Messaging based RPC subsystem processes incoming calls.')
)

expiration_token_duration = cfg.IntOpt(
    'expiration_token_duration',
    default=30,
    help=_('Window of seconds to determine whether the given token is about'
           ' to expire.')
)

pecan_opts = [
    cfg.StrOpt(
        'root',
        default='mistral.api.controllers.root.RootController',
        help=_('Pecan root controller')
    ),
    cfg.ListOpt(
        'modules',
        default=["mistral.api"],
        help=_('A list of modules where pecan will search for applications.')
    ),
    cfg.BoolOpt(
        'debug',
        default=False,
        help=_('Enables the ability to display tracebacks in the browser and'
               ' interactively debug during development.')
    ),
    cfg.BoolOpt(
        'auth_enable',
        default=True,
        help=_('Enables user authentication in pecan.')
    )
]

engine_opts = [
    cfg.StrOpt('engine', default='default', help='Mistral engine plugin'),
    cfg.HostAddressOpt(
        'host',
        default='0.0.0.0',
        help=_('Name of the engine node. This can be an opaque '
               'identifier. It is not necessarily a hostname, '
               'FQDN, or IP address.')
    ),
    cfg.StrOpt(
        'topic',
        default='mistral_engine',
        help=_('The message topic that the engine listens on.')
    ),
    cfg.StrOpt('version', default='1.0', help='The version of the engine.'),
    cfg.IntOpt(
        'execution_field_size_limit_kb',
        default=1024,
        help=_('The default maximum size in KB of large text fields '
               'of runtime execution objects. Use -1 for no limit.')
    ),
    cfg.IntOpt(
        'execution_integrity_check_delay',
        default=20,
        help=_('A number of seconds since the last update of a task'
               ' execution in RUNNING state after which Mistral will'
               ' start checking its integrity, meaning that if all'
               ' associated actions/workflows are finished its state'
               ' will be restored automatically. If this property is'
               ' set to a negative value Mistral will never be doing '
               ' this check.')
    ),
    cfg.IntOpt(
        'execution_integrity_check_batch_size',
        default=5,
        min=1,
        help=_('A number of task executions in RUNNING state that the'
               ' execution integrity checker can process in a single'
               ' iteration.')
    ),
    cfg.IntOpt(
        'action_definition_cache_time',
        default=60,
        help=_('A number of seconds that indicates how long action '
               'definitions should be stored in the local cache.')
    )
]

executor_opts = [
    cfg.StrOpt(
        'type',
        choices=['local', 'remote'],
        default='remote',
        help=(
            'Type of executor. Use local to run the executor within the '
            'engine server. Use remote if the executor is launched as '
            'a separate server to run action executions.'
        )
    ),
    cfg.HostAddressOpt(
        'host',
        default='0.0.0.0',
        help=_('Name of the executor node. This can be an opaque '
               'identifier. It is not necessarily a hostname, '
               'FQDN, or IP address.')
    ),
    cfg.StrOpt(
        'topic',
        default='mistral_executor',
        help=_('The message topic that the executor listens on.')
    ),
    cfg.StrOpt(
        'version',
        default='1.0',
        help=_('The version of the executor.')
    )
]

scheduler_opts = [
    cfg.FloatOpt(
        'fixed_delay',
        default=1,
        min=0.1,
        help=(
            'Fixed part of the delay between scheduler iterations, '
            'in seconds. '
            'Full delay is defined as a sum of "fixed_delay" and a random '
            'delay limited by "random_delay".'
        )
    ),
    cfg.FloatOpt(
        'random_delay',
        default=0,
        min=0,
        help=(
            'Max value of the random part of the delay between scheduler '
            'iterations, in seconds. '
            'Full delay is defined as a sum of "fixed_delay" and a random '
            'delay limited by this property.'
        )
    ),
    cfg.IntOpt(
        'batch_size',
        default=None,
        min=1,
        help=(
            'The max number of delayed calls will be selected during '
            'a scheduler iteration. '
            'If this property equals None then there is no '
            'restriction on selection.'
        )
    ),
    cfg.FloatOpt(
        'captured_job_timeout',
        default=30,
        min=1,
        help=(
            'Defines how soon (in seconds) a scheduled job captured for '
            'processing becomes eligible for capturing by other schedulers '
            'again. This option is needed to prevent situations when a '
            'scheduler instance captured a job and failed while processing '
            'and so this job can never be processed again because it is '
            'marked as captured.'
        )
    ),
    cfg.FloatOpt(
        'pickup_job_after',
        default=60,
        min=1,
        help='Time period given to a scheduler to process a scheduled job '
             'locally before it becomes eligible for processing by other '
             'scheduler instances.'
             'For example, a job needs to run at 12:00:00. When a scheduler '
             'starts processing it it has 60 seconds (or other configured '
             'value) to complete the job. If the scheduler did not complete '
             'the job within this period it most likely means that the '
             'scheduler process crashed. In this case another scheduler '
             'instance will pick it up from the Job Store, but not earlier '
             'than 12:01:00 and try to process it.'
    )
]

cron_trigger_opts = [
    cfg.BoolOpt(
        'enabled',
        default=True,
        help=(
            'If this value is set to False then the subsystem of cron triggers'
            ' is disabled. Disabling cron triggers increases system'
            ' performance.'
        )
    ),
    cfg.IntOpt(
        'execution_interval',
        default=1,
        min=1,
        help=(
            'This setting defines how frequently Mistral checks for cron ',
            'triggers that need execution. By default this is every second ',
            'which can lead to high system load. Increasing the number will ',
            'reduce the load but also limit the minimum freqency. For ',
            'example, a cron trigger can be configured to run every second ',
            'but if the execution_interval is set to 60, it will only run ',
            'once per minute.'
        )
    )
]

event_engine_opts = [
    cfg.HostAddressOpt(
        'host',
        default='0.0.0.0',
        help=_('Name of the event engine node. This can be an opaque '
               'identifier. It is not necessarily a hostname, '
               'FQDN, or IP address.')
    ),
    cfg.HostAddressOpt(
        'listener_pool_name',
        default='events',
        help=_('Name of the event engine\'s listener pool. This can be an'
               ' opaque identifier. It is used for identifying the group'
               ' of event engine listeners in oslo.messaging.')
    ),
    cfg.StrOpt(
        'topic',
        default='mistral_event_engine',
        help=_('The message topic that the event engine listens on.')
    ),
    cfg.StrOpt(
        'event_definitions_cfg_file',
        default='/etc/mistral/event_definitions.yaml',
        help=_('Configuration file for event definitions.')
    ),
]

notifier_opts = [
    cfg.StrOpt(
        'type',
        choices=['local', 'remote'],
        default='remote',
        help=(
            'Type of notifier. Use local to run the notifier within the '
            'engine server. Use remote if the notifier is launched as '
            'a separate server to process events.'
        )
    ),
    cfg.StrOpt(
        'host',
        default='0.0.0.0',
        help=_('Name of the notifier node. This can be an opaque '
               'identifier. It is not necessarily a hostname, '
               'FQDN, or IP address.')
    ),
    cfg.StrOpt(
        'topic',
        default='mistral_notifier',
        help=_('The message topic that the notifier server listens on.')
    ),
    cfg.ListOpt(
        'notify',
        item_type=json.loads,
        bounds=True,
        help=_('List of publishers to publish notification.')
    )
]

execution_expiration_policy_opts = [
    cfg.IntOpt(
        'evaluation_interval',
        help=_('How often will the executions be evaluated '
               '(in minutes). For example for value 120 the interval '
               'will be 2 hours (every 2 hours). '
               'Note that only final state executions will be removed: '
               '( SUCCESS / ERROR / CANCELLED ).')
    ),
    cfg.IntOpt(
        'older_than',
        help=_('Evaluate from which time remove executions in minutes. '
               'For example when older_than = 60, remove all executions '
               'that finished a 60 minutes ago or more. '
               'Minimum value is 1.')
    ),
    cfg.IntOpt(
        'max_finished_executions',
        default=0,
        help=_('The maximum number of finished workflow executions '
               'to be stored. For example when max_finished_executions = 100, '
               'only the 100 latest finished executions will be preserved. '
               'This means that even unexpired executions are eligible '
               'for deletion, to decrease the number of executions in the '
               'database. The default value is 0. If it is set to 0, '
               'this constraint won\'t be applied.')
    ),
    cfg.IntOpt(
        'batch_size',
        default=0,
        help=_('Size of batch of expired executions to be deleted.'
               'The default value is 0. If it is set to 0, '
               'size of batch is total number of expired executions '
               'that is going to be deleted.')
    )
]

action_heartbeat_opts = [
    cfg.IntOpt(
        'max_missed_heartbeats',
        min=0,
        default=15,
        help=_('The maximum amount of missed heartbeats to be allowed. '
               'If set to 0 then this feature is disabled. '
               'See check_interval for more details.')
    ),
    cfg.IntOpt(
        'check_interval',
        min=0,
        default=20,
        help=_('How often (in seconds) action executions are checked. '
               'For example when check_interval is 10, check action '
               'executions every 10 seconds. When the checker runs it will '
               'transit all running action executions to error if the last '
               'heartbeat received is older than 10 * max_missed_heartbeats '
               'seconds. If set to 0 then this feature is disabled.')
    ),
    cfg.IntOpt(
        'batch_size',
        min=0,
        default=10,
        help=_('The maximum number of action executions processed during '
               'one iteration of action execution heartbeat checker. If set '
               'to 0 then there is no limit.')
    ),
    cfg.IntOpt(
        'first_heartbeat_timeout',
        min=0,
        default=3600,
        help=_('The first heartbeat is handled differently, to provide a '
               'grace period in case there is no available executor to handle '
               'the action execution. For example when '
               'first_heartbeat_timeout = 3600, wait 3600 seconds before '
               'closing the action executions that never received a heartbeat.'
               )
    )
]

coordination_opts = [
    cfg.StrOpt(
        'backend_url',
        help=_('The backend URL to be used for coordination')
    ),
    cfg.FloatOpt(
        'heartbeat_interval',
        default=5.0,
        help=_('Number of seconds between heartbeats for coordination.')
    )
]

profiler_opts = profiler.list_opts()[0][1]
profiler_opts.append(
    cfg.StrOpt(
        'profiler_log_name',
        default='profiler_trace',
        help=_('Logger name for the osprofiler trace output.')
    )
)

keycloak_oidc_opts = [
    cfg.StrOpt(
        'auth_url',
        help=_('Keycloak base url (e.g. https://my.keycloak:8443/auth)')
    ),
    cfg.StrOpt(
        'certfile',
        help=_('Required if identity server requires client certificate')
    ),
    cfg.StrOpt(
        'keyfile',
        help=_('Required if identity server requires client certificate')
    ),
    cfg.StrOpt(
        'cafile',
        help=_('A PEM encoded Certificate Authority to use when verifying '
               'HTTPs connections. Defaults to system CAs.')
    ),
    cfg.BoolOpt(
        'insecure',
        default=False,
        help=_('If True, SSL/TLS certificate verification is disabled')
    ),
    cfg.StrOpt(
        'user_info_endpoint_url',
        default='/realms/%s/protocol/openid-connect/userinfo',
        help='Endpoint against which authorization will be performed'
    ),
]

openstack_actions_opts = [
    cfg.StrOpt(
        'os-actions-endpoint-type',
        default=os.environ.get('OS_ACTIONS_ENDPOINT_TYPE', 'public'),
        choices=['public', 'admin', 'internal'],
        deprecated_group='DEFAULT',
        help=_('Type of endpoint in identity service catalog to use for'
               ' communication with OpenStack services.')
    ),
    cfg.ListOpt(
        'modules-support-region',
        default=['nova', 'glance', 'heat', 'neutron', 'cinder',
                 'trove', 'ironic', 'designate', 'murano', 'tacker', 'senlin',
                 'aodh', 'gnocchi'],
        help=_('List of module names that support region in actions.')
    ),
    cfg.StrOpt(
        'default_region',
        help=_('Default region name for openstack actions supporting region.')
    ),
]

# note: this command line option is used only from sync_db and
# mistral-db-manage
os_actions_mapping_path = cfg.StrOpt(
    'openstack_actions_mapping_path',
    short='m',
    metavar='MAPPING_PATH',
    default='actions/openstack/mapping.json',
    help='Path to openstack action mapping json file.'
         'It could be relative to mistral package '
         'directory or absolute.'
)

yaql_opts = [
    cfg.IntOpt(
        'limit_iterators',
        default=-1,
        min=-1,
        help=_('Limit iterators by the given number of elements. When set, '
               'each time any function declares its parameter to be iterator, '
               'that iterator is modified to not produce more than a given '
               'number of items. If not set (or set to -1) the result data is '
               'allowed to contain endless iterators that would cause errors '
               'if the result where to be serialized.')
    ),
    cfg.IntOpt(
        'memory_quota',
        default=-1,
        min=-1,
        help=_('The memory usage quota (in bytes) for all data produced by '
               'the expression (or any part of it). -1 means no limitation.')
    ),
    cfg.BoolOpt(
        'convert_tuples_to_lists',
        default=True,
        help=_('When set to true, yaql converts all tuples in the expression '
               'result to lists.')
    ),
    cfg.BoolOpt(
        'convert_sets_to_lists',
        default=False,
        help=_('When set to true, yaql converts all sets in the expression '
               'result to lists. Otherwise the produced result may contain '
               'sets that are not JSON-serializable.')
    ),
    cfg.BoolOpt(
        'iterable_dicts',
        default=False,
        help=_('When set to true, dictionaries are considered to be iterable '
               'and iteration over dictionaries produces their keys (as in '
               'Python and yaql 0.2).')
    ),
    cfg.StrOpt(
        'keyword_operator',
        default='=>',
        help=_('Allows one to configure keyword/mapping symbol. '
               'Ability to pass named arguments can be disabled altogether '
               'if empty string is provided.')
    ),
    cfg.BoolOpt(
        'allow_delegates',
        default=False,
        help=_('Enables or disables delegate expression parsing.')
    )
]

CONF = cfg.CONF

API_GROUP = 'api'
ENGINE_GROUP = 'engine'
EXECUTOR_GROUP = 'executor'
SCHEDULER_GROUP = 'scheduler'
CRON_TRIGGER_GROUP = 'cron_trigger'
EVENT_ENGINE_GROUP = 'event_engine'
NOTIFIER_GROUP = 'notifier'
PECAN_GROUP = 'pecan'
COORDINATION_GROUP = 'coordination'
EXECUTION_EXPIRATION_POLICY_GROUP = 'execution_expiration_policy'
ACTION_HEARTBEAT_GROUP = 'action_heartbeat'
PROFILER_GROUP = profiler.list_opts()[0][0]
KEYCLOAK_OIDC_GROUP = "keycloak_oidc"
OPENSTACK_ACTIONS_GROUP = 'openstack_actions'
YAQL_GROUP = "yaql"
KEYSTONE_GROUP = "keystone"


CONF.register_opt(wf_trace_log_name_opt)
CONF.register_opt(auth_type_opt)
CONF.register_opt(js_impl_opt)
CONF.register_opt(rpc_impl_opt)
CONF.register_opt(rpc_response_timeout_opt)
CONF.register_opt(oslo_rpc_executor)
CONF.register_opt(expiration_token_duration)

CONF.register_opts(api_opts, group=API_GROUP)
CONF.register_opts(engine_opts, group=ENGINE_GROUP)
CONF.register_opts(executor_opts, group=EXECUTOR_GROUP)
CONF.register_opts(scheduler_opts, group=SCHEDULER_GROUP)
CONF.register_opts(cron_trigger_opts, group=CRON_TRIGGER_GROUP)
CONF.register_opts(
    execution_expiration_policy_opts,
    group=EXECUTION_EXPIRATION_POLICY_GROUP
)
CONF.register_opts(
    action_heartbeat_opts,
    group=ACTION_HEARTBEAT_GROUP
)
CONF.register_opts(event_engine_opts, group=EVENT_ENGINE_GROUP)
CONF.register_opts(notifier_opts, group=NOTIFIER_GROUP)
CONF.register_opts(pecan_opts, group=PECAN_GROUP)
CONF.register_opts(coordination_opts, group=COORDINATION_GROUP)
CONF.register_opts(profiler_opts, group=PROFILER_GROUP)
CONF.register_opts(keycloak_oidc_opts, group=KEYCLOAK_OIDC_GROUP)
CONF.register_opts(openstack_actions_opts, group=OPENSTACK_ACTIONS_GROUP)
CONF.register_opts(yaql_opts, group=YAQL_GROUP)
loading.register_session_conf_options(CONF, KEYSTONE_GROUP)

CLI_OPTS = [
    use_debugger_opt,
    launch_opt
]

default_group_opts = itertools.chain(
    CLI_OPTS,
    [
        wf_trace_log_name_opt,
        auth_type_opt,
        js_impl_opt,
        rpc_impl_opt,
        rpc_response_timeout_opt,
        oslo_rpc_executor,
        expiration_token_duration
    ]
)

CONF.register_cli_opts(CLI_OPTS)


_DEFAULT_LOG_LEVELS = [
    'eventlet.wsgi.server=WARN',
    'oslo_service.periodic_task=INFO',
    'oslo_service.loopingcall=INFO',
    'mistral.services.periodic=INFO',
    'kazoo.client=WARN',
    'oslo_db=WARN'
]


def list_opts():
    return [
        (API_GROUP, api_opts),
        (ENGINE_GROUP, engine_opts),
        (EXECUTOR_GROUP, executor_opts),
        (EVENT_ENGINE_GROUP, event_engine_opts),
        (SCHEDULER_GROUP, scheduler_opts),
        (CRON_TRIGGER_GROUP, cron_trigger_opts),
        (NOTIFIER_GROUP, notifier_opts),
        (PECAN_GROUP, pecan_opts),
        (COORDINATION_GROUP, coordination_opts),
        (EXECUTION_EXPIRATION_POLICY_GROUP, execution_expiration_policy_opts),
        (PROFILER_GROUP, profiler_opts),
        (KEYCLOAK_OIDC_GROUP, keycloak_oidc_opts),
        (OPENSTACK_ACTIONS_GROUP, openstack_actions_opts),
        (YAQL_GROUP, yaql_opts),
        (ACTION_HEARTBEAT_GROUP, action_heartbeat_opts),
        (None, default_group_opts)
    ]


def parse_args(args=None, usage=None, default_config_files=None):
    default_log_levels = log.get_default_log_levels()
    default_log_levels.extend(_DEFAULT_LOG_LEVELS)
    log.set_defaults(default_log_levels=default_log_levels)

    log.register_options(CONF)

    CONF(
        args=args,
        project='mistral',
        version=version.version_string,
        usage=usage,
        default_config_files=default_config_files
    )


def set_config_defaults():
    """This method updates all configuration default values."""
    set_cors_middleware_defaults()


def set_cors_middleware_defaults():
    """Update default configuration options for oslo.middleware."""
    cors.set_defaults(
        allow_headers=['X-Auth-Token',
                       'X-Identity-Status',
                       'X-Roles',
                       'X-Service-Catalog',
                       'X-User-Id',
                       'X-Tenant-Id',
                       'X-Project-Id',
                       'X-User-Name',
                       'X-Project-Name'],
        allow_methods=['GET',
                       'PUT',
                       'POST',
                       'DELETE',
                       'PATCH'],
        expose_headers=['X-Auth-Token',
                        'X-Subject-Token',
                        'X-Service-Token',
                        'X-Project-Id',
                        'X-User-Name',
                        'X-Project-Name']
    )
