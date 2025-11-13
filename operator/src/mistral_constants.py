"""
Module for Mistral constants
"""
import os
from kubernetes.client import V1Probe, V1ExecAction, V1HTTPGetAction, \
    V1TCPSocketAction

LIVENESS_PROBE_COMMAND = [
    "/bin/sh",
    "-c",
    "/opt/mistral/liveness_probe.sh"
]

READINESS_PROBE_COMMAND = [
    "echo",
    "ready"
]

LIVENESS_PROBE_COMMAND_RMQ = [
    "rabbitmq-diagnostics",
    "-q",
    "ping"
]


def get_liveness_probe_kafka():
    return V1Probe(
        failure_threshold=30,
        initial_delay_seconds=0,
        period_seconds=5,
        success_threshold=1,
        timeout_seconds=5,
        _exec=V1ExecAction(
            command=[
                "/bin/sh",
                "-c",
                "python3 /opt/mistral/mistral/services/" +
                "healthcheck_kafka_consumer.py || exit 1"
            ]
        )
    )


READINESS_PROBE_COMMAND_RMQ = [
    "rabbitmq-diagnostics",
    "-q",
    "check_local_alarms"
]

READINESS_PROBE = V1Probe(failure_threshold=30,
                          initial_delay_seconds=0,
                          period_seconds=5, success_threshold=1,
                          timeout_seconds=2,
                          _exec=V1ExecAction(
                              command=READINESS_PROBE_COMMAND))

LIVENESS_PROBE = V1Probe(failure_threshold=30,
                         initial_delay_seconds=0,
                         period_seconds=5, success_threshold=1,
                         timeout_seconds=2,
                         _exec=V1ExecAction(
                             command=LIVENESS_PROBE_COMMAND))

READINESS_PROBE_API = V1Probe(failure_threshold=24,
                              initial_delay_seconds=0,
                              period_seconds=5, success_threshold=1,
                              timeout_seconds=2,
                              http_get=V1HTTPGetAction(path='/v2',
                                                       port=8989,
                                                       scheme='HTTP'))

def get_readiness_probe_api(scheme):
    return V1Probe(failure_threshold=24,
                   initial_delay_seconds=0,
                   period_seconds=5, success_threshold=1,
                   timeout_seconds=2,
                   http_get=V1HTTPGetAction(path='/v2',
                                            port=8989,
                                            scheme=scheme))

LIVENESS_PROBE_API = V1Probe(failure_threshold=12,
                             initial_delay_seconds=0,
                             period_seconds=5, success_threshold=1,
                             timeout_seconds=5,
                             tcp_socket=V1TCPSocketAction(port=8989))

READINESS_PROBE_MONITORING = V1Probe(failure_threshold=24,
                              initial_delay_seconds=0,
                              period_seconds=5, success_threshold=1,
                              timeout_seconds=5,
                              http_get=V1HTTPGetAction(path='/health',
                                                       port=9090,
                                                       scheme='HTTP'))

def get_readiness_probe_monitoring(scheme):
    return V1Probe(failure_threshold=24,
                   initial_delay_seconds=0,
                   period_seconds=5, success_threshold=1,
                   timeout_seconds=5,
                   http_get=V1HTTPGetAction(path='/health',
                                            port=9090,
                                            scheme=scheme))

LIVENESS_PROBE_RMQ = V1Probe(failure_threshold=45,
                             initial_delay_seconds=0,
                             period_seconds=2, success_threshold=1,
                             timeout_seconds=5,
                             _exec=V1ExecAction(
                                 command=LIVENESS_PROBE_COMMAND_RMQ))

READINESS_PROBE_RMQ = V1Probe(failure_threshold=90,
                              initial_delay_seconds=0,
                              period_seconds=2, success_threshold=1,
                              timeout_seconds=5,
                              _exec=V1ExecAction(
                                  command=READINESS_PROBE_COMMAND_RMQ))

RABBITMQ_CONFIGMAP_DATA = {'advanced.config': '''[{lager,
    [{handlers,
        [{lager_console_backend,
            [{formatter_config,["[",date," ",time,"]",color,"[",severity,"] ",
                    {pid,[]},
                    " ",message,"\\n"]},
                {level,info}]}]}]
    }, {rabbit,
        [{log,
            [{file, [{file, false}]}] %% Disable RabbitMQ file handler
        }]}].''',
                           'enabled_plugins': '[rabbitmq_management].',
                           'rabbitmq.conf': """
## queue master locator
queue_master_locator = min-masters

## enable guest user
loopback_users.guest = false
## logging
log.console = false

log.upgrade.level = none

log.upgrade.file = false

log.file = false"""}


class Status:
    IN_PROGRESS = "In Progress"
    SUCCESSFUL = "Successful"
    FAILED = "Failed"


LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
CR_VERSION = "v2"
CR_GROUP = "qubership.org"
CR_PLURAL = "mistralservices"
CR_NAME = "mistral-service"
ALPH = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#~=_!"
POSITIVE_VALUES = ('true', 'True', 'yes', 'Yes')
OPERATOR_NEED_TO_DELETE_RESOURCES = os.getenv(
    "OPERATOR_DELETE_RESOURCES", "False")
IDP_SECRET_API_GROUP = os.getenv(
    "IDP_SECRET_API_GROUP", "qubership.org")
ADDITIONAL_CONFIGS_FILE_PATH = 'custom-mistral-service.conf'
CUSTOM_CONFIG = "custom-config"
CUSTOM_CONFIG_API = "custom-config-api"
CUSTOM_CONFIG_ENGINE = "custom-config-engine"
CUSTOM_CONFIG_EXECUTOR = "custom-config-executor"
CUSTOM_CONFIG_NOTIFIER = "custom-config-notifier"
CUSTOM_CONFIG_FILE_PATH = "custom-mistral.conf"
CUSTOM_CONFIGMAP = 'custom-mistral.conf'
COMMON_CONFIGMAP = 'mistral-common-params'
MONITORING_SERVICE = 'mistral-monitoring'
MISTRAL_TESTS = 'mistral-tests'
UPDATE_DB_JOB = 'mistral-update-db'
CLEANUP_JOB = 'mistral-cleanup-job'
MISTRAL_DR_JOB = 'mistral-dr'
MISTRAL_SECRET = 'mistral-secret'
MISTRAL_TLS_SECRET = 'mistral-tls-secret'
MISTRAL_TLS_CA_PATH = '/opt/mistral/mount_configs/tls/ca.crt'

MISTRAL_LITE_DEPLOYMENT = MISTRAL_LABEL = MISTRAL_SERVICE = "mistral"
SERVICE_ACCOUNT = MISTRAL_OPERATOR = "mistral-operator"
SELECTOR = "mistral-api"
MISTRAL_CUSTOM_CONFIG_VOLUME = "mistral-custom-config-volume"
MISTRAL_TLS_CONFIG_VOLUME = "mistral-tls-config-volume"
CLOUD_CORE_SECRET = 'mistral-client-credentials'
RABBIT_CONFIGMAP = 'rabbitmq-config'
MISTRAL_SERVICES = ['mistral-api', 'mistral-notifier', 'mistral-executor',
                    'mistral-monitoring', 'mistral-engine']
SERVICES_NAME_TO_SERVER = {'mistral-api': 'Api',
                           'mistral-notifier': 'Notifier',
                           'mistral-executor': 'Executor',
                           'mistral-monitoring': 'Monitoring',
                           'mistral-engine': 'Engine'}
DEFAULT_VHOST = '/'

if os.path.exists('/opt/operator/mount_secrets'):
    secretnames = os.listdir('/opt/operator/mount_secrets')
    secret = [s for s in secretnames if '.cer' in s]
    IDP_CERT_FILE_PATH = f"/opt/operator/mount_secrets/{secret[0]}"
else:
    IDP_CERT_FILE_PATH = "/opt/operator/mount_configs/ca.crt"



MISTRAL_SCALE_DOWN_IDP_PARAMS = ["enable", "type", "idpServer", "idpExternalServer"]

