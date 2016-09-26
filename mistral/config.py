# Copyright 2013 - Mirantis, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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
import os

from oslo_config import cfg
from oslo_log import log
from oslo_middleware import cors
from osprofiler import opts as profiler

from mistral import version

# Options under default group.
launch_opt = cfg.ListOpt(
    'server',
    default=['all'],
    help='Specifies which mistral server to start by the launch script. '
         'Valid options are all or any combination of '
         'api, engine, and executor.'
)

wf_trace_log_name_opt = cfg.StrOpt(
    'workflow_trace_log_name',
    default='workflow_trace',
    help='Logger name for pretty workflow trace output.'
)

use_debugger_opt = cfg.BoolOpt(
    'use-debugger',
    default=False,
    help='Enables debugger. Note that using this option changes how the '
         'eventlet library is used to support async IO. This could result '
         'in failures that do not occur under normal operation. '
         'Use at your own risk.'
)

auth_type_opt = cfg.StrOpt(
    'auth_type',
    default='keystone',
    help='Authentication type (valid options: keystone, keycloak-oidc)'
)

api_opts = [
    cfg.StrOpt('host', default='0.0.0.0', help='Mistral API server host'),
    cfg.PortOpt('port', default=8989, help='Mistral API server port'),
    cfg.BoolOpt(
        'allow_action_execution_deletion',
        default=False,
        help='Enables the ability to delete action_execution which '
             'has no relationship with workflows.'
    ),
    cfg.BoolOpt(
        'enable_ssl_api',
        default=False,
        help='Enable the integrated stand-alone API to service requests'
             'via HTTPS instead of HTTP.'
    ),
    cfg.IntOpt(
        'api_workers',
        help='Number of workers for Mistral API service '
             'default is equal to the number of CPUs available if that can '
             'be determined, else a default worker count of 1 is returned.'
    )
]

rpc_impl_opt = cfg.StrOpt(
    'rpc_implementation',
    default='oslo',
    choices=['oslo', 'kombu'],
    help='Specifies RPC implementation for RPC client and server. Support of '
         'kombu driver is experimental.'
)

# TODO(ddeja): This config option is a part of oslo RPCClient
# It would be the best to not register it twice, rather use RPCClient somehow
rpc_response_timeout_opt = cfg.IntOpt(
    'rpc_response_timeout',
    default=60,
    help='Seconds to wait for a response from a call.'
)

os_endpoint_type = cfg.StrOpt(
    'os-actions-endpoint-type',
    default=os.environ.get('OS_ACTIONS_ENDPOINT_TYPE', 'public'),
    choices=['public', 'admin', 'internal'],
    help='Type of endpoint in identity service catalog to use for'
         ' communication with OpenStack services.'
)

expiration_token_duration = cfg.IntOpt(
    'expiration_token_duration',
    default=30,
    help='Window of seconds to determine whether the given token is about'
         ' to expire.'
)

pecan_opts = [
    cfg.StrOpt(
        'root',
        default='mistral.api.controllers.root.RootController',
        help='Pecan root controller'
    ),
    cfg.ListOpt(
        'modules',
        default=["mistral.api"],
        help='A list of modules where pecan will search for applications.'
    ),
    cfg.BoolOpt(
        'debug',
        default=False,
        help='Enables the ability to display tracebacks in the browser and'
             ' interactively debug during development.'
    ),
    cfg.BoolOpt(
        'auth_enable',
        default=True,
        help='Enables user authentication in pecan.'
    )
]

engine_opts = [
    cfg.StrOpt('engine', default='default', help='Mistral engine plugin'),
    cfg.StrOpt(
        'host',
        default='0.0.0.0',
        help='Name of the engine node. This can be an opaque '
             'identifier. It is not necessarily a hostname, '
             'FQDN, or IP address.'
    ),
    cfg.StrOpt(
        'topic',
        default='mistral_engine',
        help='The message topic that the engine listens on.'
    ),
    cfg.StrOpt('version', default='1.0', help='The version of the engine.'),
    cfg.IntOpt(
        'execution_field_size_limit_kb',
        default=1024,
        help='The default maximum size in KB of large text fields '
             'of runtime execution objects. Use -1 for no limit.'
    )
]

executor_opts = [
    cfg.StrOpt(
        'host',
        default='0.0.0.0',
        help='Name of the executor node. This can be an opaque '
             'identifier. It is not necessarily a hostname, '
             'FQDN, or IP address.'
    ),
    cfg.StrOpt(
        'topic',
        default='mistral_executor',
        help='The message topic that the executor listens on.'
    ),
    cfg.StrOpt(
        'version',
        default='1.0',
        help='The version of the executor.'
    )
]

event_engine_opts = [
    cfg.StrOpt(
        'host',
        default='0.0.0.0',
        help='Name of the event engine node. This can be an opaque '
             'identifier. It is not necessarily a hostname, '
             'FQDN, or IP address.'
    ),
    cfg.StrOpt(
        'topic',
        default='mistral_event_engine',
        help='The message topic that the event engine listens on.'
    ),
    cfg.StrOpt(
        'event_definitions_cfg_file',
        default='/etc/mistral/event_definitions.yaml',
        help='Configuration file for event definitions.'
    ),
]

execution_expiration_policy_opts = [
    cfg.IntOpt(
        'evaluation_interval',
        help='How often will the executions be evaluated '
             '(in minutes). For example for value 120 the interval '
             'will be 2 hours (every 2 hours).'
    ),
    cfg.IntOpt(
        'older_than',
        help='Evaluate from which time remove executions in minutes. '
             'For example when older_than = 60, remove all executions '
             'that finished a 60 minutes ago or more. '
             'Minimum value is 1. '
             'Note that only final state execution will remove '
             '( SUCCESS / ERROR ).'
    )
]

coordination_opts = [
    cfg.StrOpt(
        'backend_url',
        help='The backend URL to be used for coordination'
    ),
    cfg.FloatOpt(
        'heartbeat_interval',
        default=5.0,
        help='Number of seconds between heartbeats for coordination.'
    )
]

profiler_opts = profiler.list_opts()[0][1]
profiler_opts.append(
    cfg.StrOpt(
        'profiler_log_name',
        default='profiler_trace',
        help='Logger name for the osprofiler trace output.'
    )
)

keycloak_oidc_opts = [
    cfg.StrOpt(
        'auth_url',
        help='Keycloak base url (e.g. https://my.keycloak:8443/auth)'
    ),
    cfg.StrOpt(
        'insecure',
        default=False,
        help='If True, SSL/TLS certificate verification is disabled'
    )
]

CONF = cfg.CONF

API_GROUP = 'api'
ENGINE_GROUP = 'engine'
EXECUTOR_GROUP = 'executor'
EVENT_ENGINE_GROUP = 'event_engine'
PECAN_GROUP = 'pecan'
COORDINATION_GROUP = 'coordination'
EXECUTION_EXPIRATION_POLICY_GROUP = 'execution_expiration_policy'
PROFILER_GROUP = profiler.list_opts()[0][0]
KEYCLOAK_OIDC_GROUP = "keycloak_oidc"

CONF.register_opt(wf_trace_log_name_opt)
CONF.register_opt(auth_type_opt)

CONF.register_opts(api_opts, group=API_GROUP)
CONF.register_opts(engine_opts, group=ENGINE_GROUP)
CONF.register_opts(executor_opts, group=EXECUTOR_GROUP)
CONF.register_opts(
    execution_expiration_policy_opts,
    group=EXECUTION_EXPIRATION_POLICY_GROUP
)
CONF.register_opts(event_engine_opts, group=EVENT_ENGINE_GROUP)
CONF.register_opts(pecan_opts, group=PECAN_GROUP)
CONF.register_opts(coordination_opts, group=COORDINATION_GROUP)
CONF.register_opts(profiler_opts, group=PROFILER_GROUP)
CONF.register_opt(rpc_impl_opt)
CONF.register_opt(rpc_response_timeout_opt)
CONF.register_opts(keycloak_oidc_opts, group=KEYCLOAK_OIDC_GROUP)
CONF.register_opt(os_endpoint_type)
CONF.register_opt(expiration_token_duration)

CLI_OPTS = [
    use_debugger_opt,
    launch_opt
]

default_group_opts = itertools.chain(
    CLI_OPTS,
    [wf_trace_log_name_opt, auth_type_opt, rpc_impl_opt, os_endpoint_type,
     rpc_response_timeout_opt, expiration_token_duration]
)

CONF.register_cli_opts(CLI_OPTS)

_DEFAULT_LOG_LEVELS = [
    'amqp=WARN',
    'sqlalchemy=WARN',
    'oslo_messaging=INFO',
    'iso8601=WARN',
    'eventlet.wsgi.server=WARN',
    'stevedore=INFO',
    'oslo_service.periodic_task=INFO',
    'oslo_service.loopingcall=INFO',
    'mistral.services.periodic=INFO',
    'kazoo.client=WARN'
]


def list_opts():
    return [
        (API_GROUP, api_opts),
        (ENGINE_GROUP, engine_opts),
        (EXECUTOR_GROUP, executor_opts),
        (EVENT_ENGINE_GROUP, event_engine_opts),
        (PECAN_GROUP, pecan_opts),
        (COORDINATION_GROUP, coordination_opts),
        (EXECUTION_EXPIRATION_POLICY_GROUP, execution_expiration_policy_opts),
        (PROFILER_GROUP, profiler_opts),
        (KEYCLOAK_OIDC_GROUP, keycloak_oidc_opts),
        (None, default_group_opts)
    ]


def parse_args(args=None, usage=None, default_config_files=None):
    log.set_defaults(default_log_levels=_DEFAULT_LOG_LEVELS)

    log.register_options(CONF)

    CONF(
        args=args,
        project='mistral',
        version=version,
        usage=usage,
        default_config_files=default_config_files
    )


def set_config_defaults():
    """This method updates all configuration default values."""
    set_cors_middleware_defaults()


def set_cors_middleware_defaults():
    """Update default configuration options for oslo.middleware."""
    # CORS Defaults
    # TODO(krotscheck): Update with https://review.openstack.org/#/c/285368/
    cfg.set_defaults(
        cors.CORS_OPTS,
        allow_headers=[
            'X-Auth-Token', 'X-Identity-Status', 'X-Roles',
            'X-Service-Catalog', 'X-User-Id', 'X-Tenant-Id',
            'X-Project-Id', 'X-User-Name', 'X-Project-Name'
        ],
        allow_methods=[
            'GET', 'PUT', 'POST', 'DELETE', 'PATCH'
        ],
        expose_headers=[
            'X-Auth-Token', 'X-Subject-Token', 'X-Service-Token',
            'X-Project-Id', 'X-User-Name', 'X-Project-Name'
        ]
    )
