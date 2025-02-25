# Copyright 2013 - Mirantis, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
# Copyright 2019 - Nokia Networks
# Copyright 2022 - NetCracker Technology Corp.
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

import json

from keystoneauth1 import loading
from oslo_config import cfg
from oslo_log import log
from oslo_middleware import cors
from oslo_service import _options as service_opts
from osprofiler import opts as profiler

from mistral import version

from mistral._i18n import _
from mistral.workflow import states

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

legacy_action_provider_opts = [
    cfg.BoolOpt(
        'load_action_plugins',
        default=True,
        help=_(
            'If True, enables loading actions configured in the '
            'entry point "mistral.actions".'
        )
    ),
    cfg.BoolOpt(
        'load_action_generators',
        default=True,
        help=_(
            'If True, enables loading actions from action generators '
            'configured in the entry point "mistral.generators".'
        )
    ),
    cfg.BoolOpt(
        'only_builtin_actions',
        default=False,
        help=_(
            'If True, then the legacy action provider loads only '
            'the actions delivered by the Mistral project out of '
            'the box plugged in with the entry point "mistral.actions".'
            'This property is needed mostly for testing.'
        )
    ),
]

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
    ),
    cfg.StrOpt(
        'validation_mode',
        default='mandatory',
        choices=['enabled', 'mandatory', 'disabled'],
        help=_("Defines in what cases Mistral will be validating the syntax "
               "of workflow YAML definitions. If 'enabled' is set the service "
               "will be validating the syntax but only if it's not explicitly "
               "turned off in the API request. 'disabled' disables validation "
               "for all API requests. 'mandatory' enables validation for all "
               "API requests.")
    ),
    cfg.BoolOpt(
        'enable_info_endpoint',
        default=False,
        help=_('Enable API for exposing info json about '
               'current Mistral build.')
    ),
    cfg.StrOpt(
        'info_json_file_path',
        default='info.json',
        help=_("Specify the path to info json file which will be "
               "exposed via /info endpoint.")
    ),
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
    deprecated_for_removal=True,
    deprecated_reason='Kombu driver is deprecated and will be removed '
                      'in the F release cycle',
    help=_('Specifies RPC implementation for RPC client and server. '
           'Support of kombu driver is experimental.')
)

oslo_rpc_executor = cfg.StrOpt(
    'oslo_rpc_executor',
    default='threading',
    choices=['eventlet', 'threading'],
    deprecated_for_removal=True,
    deprecated_reason='This option is going to be removed from oslo.messaging',
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
    ),
    cfg.BoolOpt(
        'start_subworkflows_via_rpc',
        default=False,
        help=(
            'Enables starting subworkflows via RPC. Use "False" to start '
            'subworkflow within the same engine instance. Use "True" '
            'to start subworkflow via RPC to improve load balancing '
            'in case of several engine instances.'
        )
    ),
    cfg.StrOpt(
        'merge_strategy',
        choices=['replace', 'merge'],
        default="replace",
        help=_('Merge strategy of data inside workflow execution. '
               '(replace, merge)')
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
        help=_('Name of the executor node. This can be an any string '
               'name/identifier. It is not necessarily a hostname, '
               'FQDN, or IP address. It is also related to the "target" '
               'attribute of tasks defined in a workflow text. If "target" '
               'is defined for a task then the action of the task will be '
               'sent to one of the executors that have the same value in the '
               '"host" property.')
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

scheduler_type_opt = cfg.StrOpt(
    'scheduler_type',
    default='legacy',
    choices=['legacy', 'default'],
    help=_('The name of the scheduler implementation used in the system.')
)

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
             'starts processing it has 60 seconds (or other configured '
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
            'This setting defines how frequently Mistral checks for cron '
            'triggers that need execution. By default this is every second '
            'which can lead to high system load. Increasing the number will '
            'reduce the load but also limit the minimum freqency. For '
            'example, a cron trigger can be configured to run every second '
            'but if the execution_interval is set to 60, it will only run '
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
    ),
    cfg.ListOpt(
        'ignored_states',
        default=[],
        help='The states that the expiration policy will filter '
             'out and will not delete.'
             'Valid values are, [{}]'.format(sorted(states.TERMINAL_STATES))
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

action_logging_opts = [
    cfg.BoolOpt(
        'hide_response_body',
        default=False,
        help=(
            'If this value is set to True then HTTP action response '
            'body will be hidden in logs.'
        )
    ),
    cfg.BoolOpt(
        'hide_request_body',
        default=False,
        help=(
            'If this value is set to True then HTTP action request '
            'body will be hidden in logs.'
        )
    ),
    cfg.ListOpt(
        'sensitive_headers',
        default=[],
        help='List of sensitive headers that should be hidden in logs.'
    )
]

context_versioning_opts = [
    cfg.BoolOpt(
        'enabled',
        default=True,
        help=(
            'If this value is set to True then Mistral will use '
            'versioning of context to improve results of context '
            'merging. This feature fixes some bugs with context merging '
            'but also slows down Mistral performance.'
        )
    ),
    cfg.BoolOpt(
        'hash_version_keys',
        default=True,
        help=(
            'If this value is set to True then Mistral will use '
            'md5 hashing for version keys to ensure this keys will be '
            'the same size. Disabling hashing could be useful for debug '
            'purposes, but avoid this in production, because it leads to '
            'excessive memory consumption.'
        )
    )
]

coordination_opts = [
    cfg.StrOpt(
        'backend_url',
        secret=True,
        deprecated_for_removal=True,
        deprecated_reason='Coordination will be removed from mistral code',
        help=_('The backend URL to be used for coordination')
    ),
    cfg.FloatOpt(
        'heartbeat_interval',
        default=5.0,
        deprecated_for_removal=True,
        deprecated_reason='This option has been unused and has had no effect',
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
    cfg.StrOpt(
        'public_cert_url',
        default="/realms/%s/protocol/openid-connect/certs",
        help="URL to get the public key for a particular realm"
    ),
    cfg.StrOpt(
        'keycloak_iss',
        help="Keycloak issuer(iss) url. "
             "Example: https://ip_add:port/auth/realms/%s"
    )
]


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
        'convert_input_data',
        default=True,
        help=_('Enables input data conversion for YAQL expressions. If set '
               'to True, YAQL will convert mutable data structures '
               '(lists, dicts, sets) into their immutable versions. That '
               'will allow them to work with some constructs that require '
               'hashable types even if elements are not hashable. For '
               'example, it will be possible to put dicts into a set. '
               'Although it conflicts with the base principles of such '
               'collections (e.g. we cannot put a non-hashable type into '
               'a set just because otherwise it will not work correctly) the '
               'YAQL library itself allows this. '
               'Disabling input data conversion may give significant '
               'performance boost if the input data for an expression is '
               'large.')
    ),
    cfg.BoolOpt(
        'convert_output_data',
        default=True,
        help=_('Enables output data conversion for YAQL expressions.'
               'If set to False, it is possible that YAQL will generate '
               'an output that will be not JSON-serializable. For example, '
               'if an expression has ".toSet()" in the end to convert a list '
               'into a set. It does not mean though that such functions '
               'cannot be used, they can still be used in expressions but '
               'user has to keep in mind of what type a result will be, '
               'whereas if the value of ths property is True YAQL will '
               'convert the result to a JSON-compatible type.')
    ),
    cfg.BoolOpt(
        'convert_tuples_to_lists',
        default=True,
        help=_('When set to True, yaql converts all tuples in the expression '
               'result to lists. It works only if "convert_output_data" is '
               'set to True.')
    ),
    cfg.BoolOpt(
        'convert_sets_to_lists',
        default=False,
        help=_('When set to True, yaql converts all sets in the expression '
               'result to lists. Otherwise the produced result may contain '
               'sets that are not JSON-serializable. It works only if '
               '"convert_output_data" is set to True.')
    ),
    cfg.BoolOpt(
        'iterable_dicts',
        default=False,
        help=_('When set to True, dictionaries are considered to be iterable '
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


healthcheck_opts = [
    cfg.BoolOpt('enabled',
                default=False,
                help=_('Enable the health check endpoint at /healthcheck. '
                       'Note that this is unauthenticated. More information '
                       'is available at '
                       'https://docs.openstack.org/oslo.middleware/latest/'
                       'reference/healthcheck_plugins.html.')),
]

CONF = cfg.CONF

LEGACY_ACTION_PROVIDER_GROUP = 'legacy_action_provider'
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
ACTION_LOGGING_GROUP = 'action_logging'
CONTEXT_VERSIONING_GROUP = 'context_versioning'
PROFILER_GROUP = profiler.list_opts()[0][0]
KEYCLOAK_OIDC_GROUP = "keycloak_oidc"
YAQL_GROUP = "yaql"
HEALTHCHECK_GROUP = 'healthcheck'
KEYSTONE_GROUP = "keystone"


CONF.register_opt(wf_trace_log_name_opt)
CONF.register_opt(auth_type_opt)
CONF.register_opt(scheduler_type_opt)
CONF.register_opt(js_impl_opt)
CONF.register_opt(rpc_impl_opt)
CONF.register_opt(oslo_rpc_executor)
CONF.register_opt(expiration_token_duration)
CONF.register_opts(service_opts.service_opts)

CONF.register_opts(
    legacy_action_provider_opts,
    group=LEGACY_ACTION_PROVIDER_GROUP
)
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
CONF.register_opts(action_logging_opts, group=ACTION_LOGGING_GROUP)
CONF.register_opts(context_versioning_opts, group=CONTEXT_VERSIONING_GROUP)
CONF.register_opts(event_engine_opts, group=EVENT_ENGINE_GROUP)
CONF.register_opts(notifier_opts, group=NOTIFIER_GROUP)
CONF.register_opts(pecan_opts, group=PECAN_GROUP)
CONF.register_opts(coordination_opts, group=COORDINATION_GROUP)
CONF.register_opts(profiler_opts, group=PROFILER_GROUP)
CONF.register_opts(keycloak_oidc_opts, group=KEYCLOAK_OIDC_GROUP)
CONF.register_opts(yaql_opts, group=YAQL_GROUP)
CONF.register_opts(healthcheck_opts, group=HEALTHCHECK_GROUP)
loading.register_session_conf_options(CONF, KEYSTONE_GROUP)

CLI_OPTS = [
    use_debugger_opt,
    launch_opt
]

default_group_opts = CLI_OPTS + [
    wf_trace_log_name_opt,
    auth_type_opt,
    scheduler_type_opt,
    js_impl_opt,
    rpc_impl_opt,
    oslo_rpc_executor,
    expiration_token_duration
]


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
        (YAQL_GROUP, yaql_opts),
        (HEALTHCHECK_GROUP, healthcheck_opts),
        (ACTION_HEARTBEAT_GROUP, action_heartbeat_opts),
        (ACTION_LOGGING_GROUP, action_logging_opts),
        (CONTEXT_VERSIONING_GROUP, context_versioning_opts),
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
