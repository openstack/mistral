"""
Module to handle create, update, delete on CR
"""
from time import sleep

import kopf
import logging
import os

from kubernetes import config as k8s_config
from kubernetes.client.exceptions import ApiException

import mistral_constants as MC
from kubernetes_helper import KubernetesHelper

logging.basicConfig(
    filename='/proc/1/fd/1',
    filemode='w',
    level=MC.LOGLEVEL,
    format='[%(asctiivsh0819me)s][%(levelname)-5s]'
           '[category=%(name)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)
logger.setLevel(MC.LOGLEVEL)
logger.info("loglevel is set to %s", str(MC.LOGLEVEL))
logger.info('OPERATOR_DELETE_RESOURCES is set '
            'to %s', MC.OPERATOR_NEED_TO_DELETE_RESOURCES)

OPTIONAL_DELETE = True
FORCED_UPGRADE = True
if MC.OPERATOR_NEED_TO_DELETE_RESOURCES in MC.POSITIVE_VALUES:
    OPTIONAL_DELETE = False

try:
    k8s_config.load_incluster_config()
except k8s_config.ConfigException:
    import sys

    logger.exception(
        "Can't load incluster kubernetes config. "
        "This script is intended to use inside of kubernetes")
    sys.exit(1)

# Code to handle MANOPD-85447 - image upgrade issue
if FORCED_UPGRADE:
    import datetime
    kube_helper = KubernetesHelper(None)
    for i in range(5):
        try:
            cr = kube_helper.get_custom_resource()
            if cr:
                cr["spec"]['mistral']['lastUpdate'] = datetime.datetime.now()
                kube_helper.update_custom_resource(cr)
            break
        except ApiException as e:
            logger.error(f'Error while fetching CR {e}')
        sleep(10)


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.scanning.disabled = True


def validate_spec(spec):
    pass


@kopf.on.create(MC.CR_GROUP, MC.CR_VERSION, MC.CR_PLURAL)
def on_create(body, meta, spec, status, **kwargs):
    kub_helper = KubernetesHelper(spec)
    logger.info("New CRD is created")
    validate_spec(spec)
    kub_helper.initiate_status()
    # we do not need to create secret - it should be already present
    if not kub_helper.is_secret_present(MC.MISTRAL_SECRET):
        kub_helper.update_status(
            MC.Status.FAILED,
            "Error",
            "Mistral secret should be present"
        )
        sleep(5)
        raise kopf.PermanentError("please create Mistral secret.")
    kub_helper.generate_idp_params()
    kub_helper.update_mistral_common_configmap()
    if kub_helper.is_mistral_lite():
        kub_helper.delete_lite_deployment(MC.MISTRAL_LITE_DEPLOYMENT)
        kub_helper.apply_lite_deployment_config(MC.MISTRAL_LITE_DEPLOYMENT)
    else:
        if kub_helper.should_cleanup():
            kub_helper.cleanup_job()
        kub_helper.create_rabbit_credentials()
        if not kub_helper.check_if_rmq_exchange_durable():
            kub_helper.scale_down_mistral_deployments()
            kub_helper.delete_existing_queues()
        kub_helper.update_db_job()
        for service in MC.MISTRAL_SERVICES:
            if kub_helper.is_deployment_present(service):
                kub_helper.update_deployment(
                    service,
                    MC.SERVICES_NAME_TO_SERVER[service]
                )
            else:
                kub_helper.apply_deployment_config(
                    service,
                    MC.SERVICES_NAME_TO_SERVER[service]
                )
    if not kub_helper.is_service_present(MC.MONITORING_SERVICE):
        kub_helper.create_mistral_monitoring_service()
    if not kub_helper.is_service_present(MC.MISTRAL_SERVICE):
        kub_helper.create_mistral_service()
    kub_helper.set_deploy_status_and_run_tests()


def spec_filter_with_excluded_field(diff, excluded_field: str) -> bool:
    events = [event for event in diff if event[1][0] == 'spec']
    logger.info("events for update: %s", str(events))
    if len(events) == 1 and events[0][0] == 'change' and events[0][1][1] == excluded_field:
        return False
    if len(events) == 2 and events[0][0] == 'add' and events[0][1][1] == excluded_field \
            and events[1][0] == 'change' and events[1][1][1] == excluded_field:
        return False
    elif len(events):
        return True
    return False


def check_for_operator_id(spec):
    operator_id = os.getenv("OPERATOR_ID", "")
    cr_operator_id = spec.get("operatorId", "")
    return operator_id == cr_operator_id


def check_if_mistral_scale_down_needed(kube_helper, diff):
    changed_parameters = [
        change[1][-1] for change in diff
        if change[1][-1] in MC.MISTRAL_SCALE_DOWN_IDP_PARAMS]
    if kube_helper.is_auth_enabled() and (
            changed_parameters or kube_helper.is_secret_updated(MC.MISTRAL_SECRET)):
        return True
    else:
        return False


def exclude_disaster_recovery_field(spec, diff, **kwargs):
    return spec_filter_with_excluded_field(diff, 'disasterRecovery')


@kopf.on.update(MC.CR_GROUP, MC.CR_VERSION, MC.CR_PLURAL, when=exclude_disaster_recovery_field)
def on_update(body, meta, spec, status, old, new, diff, **kwargs):
    if not check_for_operator_id(spec):
        logger.info("New Mistral operator deployment discovered, awaiting deployment"
                    " readiness is established.")
        sleep(90)
        return
    kub_helper = KubernetesHelper(spec)

    mode = spec.get('disasterRecovery').get('mode', None)
    if mode == 'standby' or mode == 'disable':
        kub_helper.update_status(
            MC.Status.SUCCESSFUL,
            f"DR mode is: {mode}",
            f"Mistral operator skipped reconcile process"
        )
        return

    logger.info("changes: %s", str(diff))
    logger.info('Handling the diff')
    kub_helper.update_status(
        MC.Status.IN_PROGRESS,
        "",
        f"Mistral operator started deploy process"
    )
    if not kub_helper.is_secret_present(MC.MISTRAL_SECRET):
        kub_helper.update_status(
            MC.Status.FAILED,
            "Error",
            "Mistral secret should be present"
        )
        sleep(5)
        raise kopf.PermanentError("please create Mistral secret.")
    if kub_helper.integration_tests_enabled() and kub_helper.run_tests_only():
        kub_helper.set_deploy_status_and_run_tests()
        return
    idp_updated = kub_helper.generate_idp_params()
    if kub_helper.is_deployment_present(MC.MISTRAL_TESTS):
        kub_helper.delete_deployment(MC.MISTRAL_TESTS, True)
        sleep(5)
    kub_helper.update_mistral_common_configmap()
    if kub_helper.is_mistral_lite():
        kub_helper.update_lite_deployment(MC.MISTRAL_LITE_DEPLOYMENT)
    else:
        kub_helper.create_rabbit_credentials()
        if not kub_helper.check_if_rmq_exchange_durable() or idp_updated or \
            check_if_mistral_scale_down_needed(kub_helper, diff):
            kub_helper.scale_down_mistral_deployments()
            kub_helper.delete_existing_queues()
        kub_helper.update_db_job()
        for service in MC.MISTRAL_SERVICES:
            if kub_helper.is_deployment_present(service):
                kub_helper.update_deployment(
                    service,
                    MC.SERVICES_NAME_TO_SERVER[service]
                )
            else:
                kub_helper.apply_deployment_config(
                    service,
                    MC.SERVICES_NAME_TO_SERVER[service]
                )

    if not kub_helper.is_service_present(MC.MONITORING_SERVICE):
        kub_helper.create_mistral_monitoring_service()
    if not kub_helper.is_service_present(MC.MISTRAL_SERVICE):
        kub_helper.create_mistral_service()
    kub_helper.set_deploy_status_and_run_tests()


@kopf.on.delete(MC.CR_GROUP, MC.CR_VERSION, MC.CR_PLURAL, optional=OPTIONAL_DELETE)
@kopf.on.delete(MC.CR_GROUP, MC.CR_VERSION, MC.CR_PLURAL, optional=OPTIONAL_DELETE)
def on_delete(spec, **kwargs):
    logger.info('Deleting Mistral')
    kub_helper = KubernetesHelper(spec)
    if kub_helper.is_secret_present(MC.MISTRAL_SECRET):
        kub_helper.delete_mistral_secret()
    if kub_helper.is_configmap_present(MC.COMMON_CONFIGMAP):
        kub_helper.delete_configmap(MC.COMMON_CONFIGMAP)
    if kub_helper.is_configmap_present(MC.CUSTOM_CONFIGMAP):
        kub_helper.delete_configmap(MC.CUSTOM_CONFIGMAP)
    if kub_helper.is_db_update_job_present():
        kub_helper.delete_db_job()
    for service in MC.MISTRAL_SERVICES:
        if kub_helper.is_deployment_present(service):
            kub_helper.delete_deployment(service)
    if kub_helper.is_service_present(MC.MISTRAL_SERVICE):
        kub_helper.delete_mistral_service()
    if kub_helper.is_mistral_lite():
        kub_helper.delete_lite_deployment(MC.MISTRAL_LITE_DEPLOYMENT)


@kopf.on.field(MC.CR_GROUP, MC.CR_VERSION, MC.CR_PLURAL, field='spec.disasterRecovery.mode')
def set_disaster_recovery_state(spec, status, namespace, diff, **kwargs):
    mode = spec.get('disasterRecovery').get('mode', None)
    if mode is None:
        raise kopf.PermanentError("disaster recovery mode is not specified")
    no_wait: bool = spec.get('disasterRecovery').get('noWait', False)
    status_mode = status.get('disasterRecoveryStatus', None)
    if status_mode is not None:
        status_mode = status_mode.get('mode', None)
    kub_helper = KubernetesHelper(spec)
    kub_helper.update_disaster_recovery_status(
        mode=mode,
        status="running",
        message="The switchover process for Mistral Service has been started")

    status = "done"
    message = "success installation"
    try:
        logger.info(f"Start switchover with mode: {mode} and no-wait: {no_wait},"
                    f" current status mode is: {status_mode}")
        if mode == 'standby' or mode == 'disable':
            kub_helper.scale_down_mistral_deployments()
            kub_helper.update_status(
                MC.Status.SUCCESSFUL,
                f"DR mode is: {mode}",
                f"Mistral operator skipped reconcile process"
            )

        if mode == 'active':
            if status_mode is not None:
                kub_helper.mistral_dr_job()
                kub_helper.scale_up_mistral_deployments()

    except Exception as e:
        status = "failed"
        message = e.__str__()
        logger.error(f"Switchover failed: {message}")
    kub_helper.update_disaster_recovery_status(mode=mode, status=status,
                                               message=message)
    logger.info("Switchover finished successfully")
