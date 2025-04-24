#!/usr/bin/env python3

from confluent_kafka.admin import AdminClient
import os
import sys


def get_env(name, default=None, required=True):
    val = os.getenv(name, default)
    if required and val is None:
        print(f"Missing required env var: {name}")
        sys.exit(1)
    return val


def main():
    kafka_host = get_env("KAFKA_HOST")
    group_id = get_env("KAFKA_CONSUMER_GROUP_ID")
    security_enabled = os.getenv("KAFKA_SECURITY_ENABLED", "false").\
        lower() == "true"
    tls_enabled = os.getenv("KAFKA_TLS_ENABLED", "false").lower() == "true"

    conf = {
        "bootstrap.servers": kafka_host,
        "group.id": group_id
    }

    if security_enabled:
        conf.update({
            "sasl.mechanism": "SCRAM-SHA-512",
            "security.protocol": "SASL_PLAINTEXT",
            "sasl.username": get_env("KAFKA_SASL_PLAIN_USERNAME"),
            "sasl.password": get_env("KAFKA_SASL_PLAIN_PASSWORD"),
        })

    if tls_enabled:
        conf['security.protocol'] = 'SASL_SSL' if security_enabled else 'SSL'
        conf['enable.ssl.certificate.verification'] = True
        conf['ssl.ca.location'] = '/opt/mistral/mount_configs/tls/ca.crt'
        conf['ssl.key.location'] = '/opt/mistral/mount_configs/tls/tls.key'
        conf[
            'ssl.certificate.location'
        ] = '/opt/mistral/mount_configs/tls/tls.crt'

    try:
        admin = AdminClient(conf)
        groups = admin.list_groups(timeout=10)

        target_group = next((g for g in groups if g.id == group_id), None)

        if not target_group:
            print(f"Consumer group '{group_id}' not found.")
            sys.exit(1)

        if not target_group.members:
            print(f"Consumer group '{group_id}' has no active members.")
            sys.exit(1)

        print(f"Consumer group '{group_id}' has {len(target_group.members)}" +
              " active member(s).")
        sys.exit(0)

    except Exception as e:
        print(f"Error checking Kafka group: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
