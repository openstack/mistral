# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import confluent_kafka as ck
from confluent_kafka.admin import AdminClient
from confluent_kafka.admin import NewPartitions
from confluent_kafka.admin import NewTopic
from confluent_kafka import Consumer
from confluent_kafka import KafkaException
from confluent_kafka import Producer


import datetime
import eventlet
from eventlet import Semaphore
import json
import sys
import time

from mistral import context as auth_ctx

from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

__PRODUCER = None
__CONSUMER = None

__NOTIFIER = None

__sem = Semaphore()

__PRODUCER_CHECK_TIME = None


def _get_basic_conf():
    host = cfg.CONF.kafka_notifications.kafka_host

    conf = {
        'bootstrap.servers': host
    }

    security_enabled = cfg.CONF.kafka_notifications.kafka_security_enabled

    if security_enabled:
        username = cfg.CONF.kafka_notifications.kafka_sasl_plain_username
        password = cfg.CONF.kafka_notifications.kafka_sasl_plain_password
        conf['sasl.mechanism'] = 'SCRAM-SHA-512'
        conf['security.protocol'] = 'SASL_PLAINTEXT'
        conf['sasl.username'] = username
        conf['sasl.password'] = password

    tls_enabled = cfg.CONF.kafka_notifications.kafka_tls_enabled

    if tls_enabled:
        conf['security.protocol'] = 'SASL_SSL' if security_enabled else 'SSL'
        conf['enable.ssl.certificate.verification'] = True
        conf['ssl.ca.location'] = '/opt/mistral/mount_configs/tls/ca.crt'
        conf['ssl.key.location'] = '/opt/mistral/mount_configs/tls/tls.key'
        conf[
            'ssl.certificate.location'
        ] = '/opt/mistral/mount_configs/tls/tls.crt'

    return conf


def _get_producer():
    global __PRODUCER
    if not __PRODUCER:
        conf = _get_basic_conf()
        conf['acks'] = 'all'

        __PRODUCER = Producer(conf, logger=LOG)

    return __PRODUCER


def _reset_producer():
    global __PRODUCER
    if __PRODUCER:
        del __PRODUCER
    __PRODUCER = None


def _reset_producer_check_time():
    global __PRODUCER_CHECK_TIME
    __PRODUCER_CHECK_TIME = None


def _mark_producer_dead_for_some_time():
    global __PRODUCER_CHECK_TIME
    LOG.info("Kafka broker seems unavailable, waiting 60 seconds to reconnect")
    __PRODUCER_CHECK_TIME = datetime.datetime.now() + datetime.timedelta(
        seconds=60
    )


def _producer_ready():
    global __PRODUCER_CHECK_TIME
    if not __PRODUCER_CHECK_TIME:
        return True
    return datetime.datetime.now() > __PRODUCER_CHECK_TIME


def send_notification(data):
    with __sem:
        try:
            if not _producer_ready():
                return False

            _reset_producer_check_time()

            topic = cfg.CONF.kafka_notifications.kafka_topic
            bdata = json.dumps(data, default=str).encode('utf-8')

            key = data['data']['id']
            if 'workflow_execution_id' in data['data']:
                key = data['data']['workflow_execution_id']

            producer = _get_producer()

            producer.produce(topic, bdata, key=key.encode('utf-8'))
            left = producer.flush(timeout=10)

            if left == 0:
                LOG.info("Notification was sent to Kafka [id=%s, event=%s]",
                         data['data']['id'], data['event'])
                return True

            _mark_producer_dead_for_some_time()
            producer.purge()
            _reset_producer()
            return False
        except (ck.KafkaError, ck.KafkaException):
            return False


def _get_consumer():
    global __CONSUMER
    if not __CONSUMER:
        topic = cfg.CONF.kafka_notifications.kafka_topic
        group_id = cfg.CONF.kafka_notifications.kafka_consumer_group_id
        max_poll_interval = \
            cfg.CONF.kafka_notifications.kafka_max_poll_interval

        conf = _get_basic_conf()
        conf['group.id'] = group_id
        conf['auto.offset.reset'] = 'smallest'
        conf['enable.auto.commit'] = False
        conf['max.poll.interval.ms'] = max_poll_interval
        conf['default.topic.config'] = {
            "topic.metadata.refresh.interval.ms": 20000
        }

        __CONSUMER = Consumer(conf, logger=LOG)
        __CONSUMER.subscribe(topics=[topic])

    return __CONSUMER


def _reset_consumer():
    global __CONSUMER
    if __CONSUMER:
        __CONSUMER.close()
    __CONSUMER = None


def listen_notifications():
    consumer_poll_timeout = \
        cfg.CONF.kafka_notifications.kafka_consumer_poll_timeout
    max_commit_interval = \
        cfg.CONF.kafka_notifications.kafka_consumer_commit_max_interval
    min_msg_count_to_commit = \
        cfg.CONF.kafka_notifications.kafka_consumer_commit_min_message_count

    last_commit_time = datetime.datetime.now()
    idle_iterations_timeout = 30
    idle_iterations = 0
    sleep_iteration = 0
    msg_count = 0
    while True:
        try:
            if sleep_iteration == 10:
                sleep_iteration = 0
                eventlet.sleep(0.3)
            else:
                sleep_iteration += 1

            msg = _get_consumer().poll(timeout=consumer_poll_timeout)
            curr_time = datetime.datetime.now()
            if msg is None:
                if idle_iterations == idle_iterations_timeout:
                    idle_iterations = 0
                    LOG.error(
                        "No messages for the long time,"
                        " reconnecting...")
                    _reset_consumer()
                    eventlet.sleep(1)
                idle_iterations += 1

            elif msg.error():
                if msg.error().code() == ck.KafkaError._PARTITION_EOF:
                    # End of partition event
                    LOG.error(
                        '%% %s [%d] reached end at offset %d\n',
                        msg.topic(), msg.partition(), msg.offset()
                    )
                elif msg.error():
                    LOG.error(msg.error())
                    LOG.error(
                        "Something went wrong with kafka consumer,"
                        " reconnecting in 5 seconds...")
                    _reset_consumer()
                    time.sleep(5)
            else:
                idle_iterations = 0
                data = json.loads(msg.value().decode('utf-8'))
                rpc_ctx = data['rpc_ctx']
                auth_ctx.set_ctx(auth_ctx.MistralContext.from_dict(rpc_ctx))
                del data['rpc_ctx']
                yield data
                msg_count += 1

            delta = curr_time - last_commit_time
            if msg_count and delta.seconds > max_commit_interval \
                    or msg_count >= min_msg_count_to_commit:
                try:
                    _get_consumer().commit(asynchronous=False)
                    last_commit_time = datetime.datetime.now()
                    LOG.info(
                        "%d messages were processed, offsets were commited.",
                        msg_count
                    )
                    msg_count = 0
                except KafkaException as e:
                    if 'NO_OFFSET' in str(e):
                        msg_count = 0
                    else:
                        raise e

        except Exception as e:
            LOG.error(e)
            LOG.error(
                "Something went wrong with kafka consumer,"
                " reconnecting in 5 seconds...")
            _reset_consumer()
            eventlet.sleep(5)


def _consume_loop():
    global __NOTIFIER
    for notification in listen_notifications():
        LOG.info("Received notification from Kafka [id=%s, event=%s]",
                 notification['data']['id'], notification['event'])
        __NOTIFIER.notify(**notification)


def init_consume_loop(notifier):
    global __NOTIFIER
    __NOTIFIER = notifier

    eventlet.spawn(_consume_loop)


def _get_admin_client():
    conf = _get_basic_conf()
    admin_client = AdminClient(conf)

    return admin_client


def _create_topic_and_partitions():
    if not cfg.CONF.kafka_notifications.enabled:
        LOG.info("Kafka notifications are disabled, skipping topic creation.")
        return

    topic = cfg.CONF.kafka_notifications.kafka_topic
    p_count = cfg.CONF.kafka_notifications.kafka_topic_partitions_count

    admin_client = _get_admin_client()

    cluster_metadata = admin_client.list_topics()
    if topic not in cluster_metadata.topics:
        LOG.info("Topic for mistral notifications is not exist. Creating...")
        n_brokers = len(cluster_metadata.brokers)
        replication_factor = n_brokers
        LOG.info("Kafka cluster has %d brokers.", n_brokers)
        if n_brokers > 3:
            replication_factor = 3
        LOG.info("Setting replication factor to %d.", replication_factor)
        LOG.info("Setting partitions num to %d.", p_count)

        new_topic = NewTopic(
            topic=topic,
            num_partitions=p_count,
            replication_factor=replication_factor
        )
        fs = admin_client.create_topics(
            [new_topic],
            operation_timeout=15
        )
        for topic, f in fs.items():
            try:
                f.result(timeout=15)
                LOG.info("Topic {} created".format(topic))
            except Exception as e:
                LOG.error("Failed to create topic {}: {}".format(topic, e))
                sys.exit(1)
        return

    LOG.info("Topic already exist. Check partitions num.")
    curr_n_partitions = len(cluster_metadata.topics[topic].partitions)

    if curr_n_partitions == p_count:
        LOG.info("Topic already has %d partitions.", p_count)
    else:
        diff = p_count - curr_n_partitions
        LOG.info("Topic has not enough partitions. Creating %d more...", diff)
        new_partitions = NewPartitions(topic, p_count)
        fs = admin_client.create_partitions(
            [new_partitions],
            operation_timeout=15
        )
        for topic, f in fs.items():
            try:
                f.result(timeout=15)  # The result itself is None
                LOG.info(
                    "Additional partitions created for topic {}".format(topic)
                )
            except Exception as e:
                LOG.error(
                    "Failed to add partitions to topic {}: {}".format(topic, e)
                )
                sys.exit(1)


def delete_topic():
    topic = cfg.CONF.kafka_notifications.kafka_topic
    admin_client = _get_admin_client()
    try:
        fs = admin_client.delete_topics([topic])

        for topic, f in fs.items():
            try:
                f.result()
                LOG.info(f"Topic {topic} has been deleted.")
            except Exception as e:
                LOG.error(f"Failed to delete topic {topic}: {e}")
                sys.exit(1)

    except Exception as e:
        LOG.error(f"Failed to initiate topic deletion {topic}: {e}")
        sys.exit(1)


def create_topic_and_partitions():
    from mistral.db.v2 import api as db_api

    with db_api.named_lock("kafka_preparation"):
        _create_topic_and_partitions()
