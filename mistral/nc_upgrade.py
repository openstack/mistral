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

try:
    from psycopg2cffi import compat
    compat.register()
except ImportError:
    pass

import os
import six
import sys

from alembic import command as alembic_cmd
from alembic import config as alembic_cfg
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2 import sql
import requests
from requests import auth
from sqlalchemy.sql import expression

from mistral.db.sqlalchemy import base as b
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.services import kafka_notifications
from mistral.services import maintenance

from alembic import util as alembic_u


DEFAULT_VHOST = '/'

MAIN_DB_NAME = 'postgres'

pg_host = os.getenv('PG_HOST', 'postgres')
pg_port = os.getenv('PG_PORT', '5432')

pg_admin_user = os.getenv('PG_ADMIN_USER', 'postgres')
pg_admin_password = os.getenv('PG_ADMIN_PASSWORD', 'postgres')

pg_user = os.getenv('PG_USER', 'postgres')
pg_password = os.getenv('PG_PASSWORD', 'postgres')
pg_db_name = os.getenv('PG_DB_NAME', 'mistral')

importutils.try_import('mistral.api.app')

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def get_curs(db_name=MAIN_DB_NAME, pg_u=pg_admin_user, pg_p=pg_admin_password):
    with psycopg2.connect(user=pg_u,
                          password=pg_p,
                          dbname=db_name,
                          host=pg_host,
                          port=pg_port) as conn:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn.cursor()


def drop_db(config, cmd):
    LOG.info("Try to drop '{}' database".format(pg_db_name))

    with get_curs() as curs:
        curs.execute("""
        SELECT pid, usename, client_addr, client_port, backend_start
        FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname=%s
        """, (pg_db_name, ))
        conn = curs.fetchall()

        if conn:
            LOG.info("There are {} active connections to this database."
                     .format(len(conn)))
            for row in conn:
                LOG.info("PID: {}; User: {} ({}:{}); Connected: {}"
                         .format(row[0], row[1], row[2], row[3], row[4]))
            sys.exit(1)

        curs.execute(sql.SQL("DROP DATABASE IF EXISTS {}")
                     .format(sql.Identifier(pg_db_name)))
        LOG.info("Database '{}' was dropped".format(pg_db_name))


def create_db(config, cmd):
    LOG.info("Try to create '{}' PostgreSQL database.".format(pg_db_name))

    with get_curs() as curs:
        curs.execute("SELECT 1 FROM pg_database WHERE datname=%s",
                     (pg_db_name,))

        if curs.fetchone() is None:
            curs.execute(sql.SQL("CREATE DATABASE {}")
                         .format(sql.Identifier(pg_db_name)))

            LOG.info('Database {} is created'.format(pg_db_name))
        else:
            LOG.info('Database {} already exists'.format(pg_db_name))


def create_user(config, cmd):
    LOG.info("Try to create '{}' PostgreSQL user".format(pg_user))
    with get_curs() as curs:
        curs.execute("SELECT * FROM pg_user WHERE usename LIKE %s", (pg_user,))

        if curs.fetchone() is None:
            curs.execute(sql.SQL("CREATE USER {} WITH PASSWORD {}")
                         .format(sql.Identifier(pg_user),
                                 sql.Literal(pg_password)))

            LOG.info('User {} is created'.format(pg_user))
        else:
            LOG.info('User {} already exists'.format(pg_user))

            curs.execute(sql.SQL("ALTER USER {} WITH PASSWORD {}")
                         .format(sql.Identifier(pg_user),
                                 sql.Literal(pg_password)))

        with get_curs(db_name=pg_db_name) as curs:
            curs.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {};")
                         .format(sql.Identifier(pg_user)))
            curs.execute(sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES\
                IN SCHEMA public TO {}")
                         .format(sql.Identifier(pg_user)))


def set_alembic_version(config, cmd):
    version = CONF.command.version
    LOG.info("Set alembic_version to {}".format(version))
    with get_curs(db_name=pg_db_name) as curs:
        curs.execute(sql.SQL("UPDATE alembic_version SET version_num = {}")
                     .format(sql.Literal(version)))


def set_nc_alembic_version(config, cmd):
    version = CONF.command.version
    LOG.info("Set nc_alembic_version to {}".format(version))
    with get_curs(db_name=pg_db_name) as curs:
        curs.execute(sql.SQL("UPDATE nc_alembic_version SET version_num = {}")
                     .format(sql.Literal(version)))


def fix_last_heartbeat(config, cmd):
    LOG.info("Change last heartbeat to vanilla impl")
    with get_curs(db_name=pg_db_name) as curs:
        curs.execute(sql.SQL(
            "ALTER TABLE action_executions_v2 DROP COLUMN last_heartbeat"
        ))


def get_current_nc_version(config, cmd):
    version = None
    with get_curs(db_name=pg_db_name) as curs:
        curs.execute(sql.SQL("SELECT version_num FROM nc_alembic_version"))
        version = curs.fetchone()[0]
    config.print_stdout(version)


def upgrade_db(config, cmd):
    try:
        getattr(alembic_cmd, 'upgrade')(config, 'head',
                                        sql=False)
    except alembic_u.CommandError as e:
        alembic_u.err(six.text_type(e))


def set_idle_timeout(config, cmd):
    timeout = os.getenv('PG_IDLE_TIMEOUT', '30s')
    LOG.info("Try to set timeout '{}' for idle session".format(timeout))
    with get_curs() as curs:
        curs.execute(sql.SQL(f'ALTER DATABASE "{pg_db_name}" \
            SET idle_in_transaction_session_timeout = "{timeout}"'))
    LOG.info('Timeout is set.')


def delete_action_definition_by_prefix(prefix):
    LOG.info('Try to delete actions with {} prefix'.format(prefix))
    try:
        b.model_query(models.ActionDefinition).filter(
            models.ActionDefinition.name.like(prefix + '.%'),
            models.ActionDefinition.is_system == expression.true()
        ).delete(synchronize_session=False)
    except Exception as e:
        LOG.info("{} Exception ".format(e))

    LOG.info('Actions with {} prefix were deleted successfully'.format(prefix))


class RabbitMQHelper(object):
    def __init__(self):
        self._host = os.getenv('RABBIT_HOST', 'localhost')
        self._vhost = os.getenv('RABBIT_VHOST', '/')
        self._user = os.getenv('RABBIT_USER', 'mistral')
        self._password = os.getenv('RABBIT_PASSWORD', 'mistral')
        self._admin_user = os.getenv('RABBIT_ADMIN_USER', 'guest')
        self._admin_password = os.getenv('RABBIT_ADMIN_PASSWORD', 'guest')
        self._queue_name_prefix = os.getenv('QUEUE_NAME_PREFIX', '')

    def create_rabbit_vhost(self):
        if self._vhost == DEFAULT_VHOST:
            LOG.info('Default vhost is used. Skip a user creation')
            return

        res = self.request(
            "vhosts/{vhost}".format(vhost=self._vhost)
        )
        res.raise_for_status()
        LOG.info('Created {} rabbit vhost'.format(self._vhost))

    def create_rabbit_user(self):
        if self._admin_user == self._user:
            LOG.info('Admin user equals user. Skip a user creation')
            return

        body = {
            'password': self._password,
            'tags': ''
        }
        res = self.request(
            url='users/' + self._user,
            json=body
        )
        res.raise_for_status()
        LOG.info('Created {} rabbit user'.format(self._user))

    def add_rabbit_permissions(self):
        if self._vhost == DEFAULT_VHOST and self._user == self._admin_user:
            LOG.info('Default user and vhost are used. Skip a set permissions')
            return

        vhost = '%2f' if self._vhost == DEFAULT_VHOST else self._vhost
        body = {
            "configure": ".*", "write": ".*", "read": ".*"
        }
        res = self.request(
            url='permissions/{vhost}/{user}'.format(
                vhost=vhost, user=self._user),
            json=body
        )
        res.raise_for_status()
        LOG.info(
            'Add {} permissions to {} vhost'.format(self._user, vhost))

    def delete_existing_queues(self):
        vhost = '%2f' if self._vhost == DEFAULT_VHOST else self._vhost
        res = self.request(
            url='queues/{vhost}'.format(vhost=vhost),
            method='GET'
        )

        res.raise_for_status()

        queues_to_delete = []

        LOG.info(
            "Searching for existing mistral "
            "queues in {} vhost with {} prefix".format(
                vhost, self._queue_name_prefix
            )
        )

        def _is_mistral_queue(name):
            if not name.startswith(self._queue_name_prefix):
                return False
            if 'mistral' not in name:
                return False
            return True

        for queue in res.json():
            if _is_mistral_queue(queue['name']):
                queues_to_delete.append(queue['name'])

        if not queues_to_delete:
            LOG.info('There are no queues to delete.')

            LOG.info('Delete openstack exchange')

            res = self.request(
                url='exchanges/{vhost}/openstack'.format(
                    vhost=vhost
                ),
                method='DELETE'
            )

            return

        LOG.info('Founded queues to delete: {}'.format(str(queues_to_delete)))

        for queue in queues_to_delete:
            res = self.request(
                url='queues/{vhost}/{name}'.format(
                    vhost=vhost, name=queue
                ),
                method='DELETE'
            )
            res.raise_for_status()

        LOG.info('Queues were deleted.')

        LOG.info('Delete openstack exchange')

        res = self.request(
            url='exchanges/{vhost}/openstack'.format(
                vhost=vhost
            ),
            method='DELETE'
        )

    def request(self, url, method='PUT', json=None):
        res = requests.request(
            url='http://' + self._host + ':15672/api/' + url,
            method=method,
            auth=auth.HTTPBasicAuth(self._admin_user, self._admin_password),
            json=json)

        return res


def create_rabbit_credentials(config, cmd):
    rq_helper = RabbitMQHelper()
    rq_helper.create_rabbit_user()
    rq_helper.create_rabbit_vhost()
    rq_helper.add_rabbit_permissions()


def delete_existing_queues(config, cmd):
    rq_helper = RabbitMQHelper()
    rq_helper.delete_existing_queues()


def prepare_kafka_if_needed(config, cmd):
    kafka_notifications.create_topic_and_partitions()


def delete_kafka_topic(config, cmd):
    kafka_notifications.delete_topic()


def create_tenant_table(config, cmd):
    with db_api.transaction():
        db_api.create_tenant_table()


def dr(config, cmd):
    db_api.update_maintenance_status(maintenance.PAUSING)

    maintenance.pause_running_executions()

    with db_api.transaction():
        if db_api.get_maintenance_status() == maintenance.PAUSING:
            db_api.update_maintenance_status(maintenance.PAUSED)


def add_command_parsers(subparsers):
    parser = subparsers.add_parser('drop_db')
    parser.set_defaults(func=drop_db)

    parser = subparsers.add_parser('create_db')
    parser.set_defaults(func=create_db)

    parser = subparsers.add_parser('create_user')
    parser.set_defaults(func=create_user)

    parser = subparsers.add_parser('upgrade_db')
    parser.set_defaults(func=upgrade_db)

    parser = subparsers.add_parser('set_idle_timeout')
    parser.set_defaults(func=set_idle_timeout)

    parser = subparsers.add_parser('set_version')
    parser.add_argument('version', nargs='?')
    parser.set_defaults(func=set_alembic_version)

    parser = subparsers.add_parser('set_nc_version')
    parser.add_argument('version', nargs='?')
    parser.set_defaults(func=set_nc_alembic_version)

    parser = subparsers.add_parser('fix_lh')
    parser.set_defaults(func=fix_last_heartbeat)

    parser = subparsers.add_parser('current')
    parser.set_defaults(func=get_current_nc_version)

    parser = subparsers.add_parser('create_rabbit_credentials')
    parser.set_defaults(func=create_rabbit_credentials)

    parser = subparsers.add_parser('dr')
    parser.set_defaults(func=dr)

    parser = subparsers.add_parser('delete_existing_queues')
    parser.set_defaults(func=delete_existing_queues)

    parser = subparsers.add_parser('prepare_kafka_if_needed')
    parser.set_defaults(func=prepare_kafka_if_needed)

    parser = subparsers.add_parser('create_tenant_table')
    parser.set_defaults(func=create_tenant_table)

    parser = subparsers.add_parser('delete_kafka_topic')
    parser.set_defaults(func=delete_kafka_topic)


def main():
    config = alembic_cfg.Config(
        os.path.join(os.path.dirname(__file__), 'alembic.ini')
    )
    config.set_main_option(
        'script_location',
        'mistral.db.sqlalchemy.nc_migration:nc_alembic_migrations'
    )

    config.mistral_config = CONF
    logging.register_options(CONF)

    CONF(project='mistral')
    logging.setup(CONF, 'Mistral')
    CONF.command.func(config, CONF.command.name)


if not CONF._args:
    command_opt = cfg.SubCommandOpt('command',
                                    title='Command',
                                    help='Available commands',
                                    handler=add_command_parsers)
    CONF.register_cli_opt(command_opt)

if __name__ == '__main__':
    sys.exit(main())
