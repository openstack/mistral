#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Starter script for mistral-db-manage."""

# NOTE(amorin)
# Hardcode the threading backend to avoid using eventlet until this will
# eventually become the default
import oslo_service.backend as service_backend
service_backend.init_backend(service_backend.BackendType.THREADING)

import os

from alembic import command as alembic_cmd
from alembic import config as alembic_cfg
from alembic import util as alembic_u
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils
import sys

from mistral.services import action_manager
from mistral.services import workflows


# We need to import mistral.api.app to
# make sure we register all needed options.
importutils.try_import('mistral.api.app')


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def do_alembic_command(config, cmd, *args, **kwargs):
    try:
        getattr(alembic_cmd, cmd)(config, *args, **kwargs)
    except alembic_u.CommandError as e:
        alembic_u.err(str(e))


def do_check_migration(config, _cmd):
    do_alembic_command(config, 'branches')


def do_upgrade(config, cmd):
    if not CONF.command.revision and not CONF.command.delta:
        raise SystemExit('You must provide a revision or relative delta')

    revision = CONF.command.revision

    if CONF.command.delta:
        sign = '+' if CONF.command.name == 'upgrade' else '-'
        revision = sign + str(CONF.command.delta)

    do_alembic_command(config, cmd, revision, sql=CONF.command.sql)


def do_stamp(config, cmd):
    do_alembic_command(
        config, cmd,
        CONF.command.revision,
        sql=CONF.command.sql
    )


def do_populate(config, cmd):
    LOG.info("Populating db")
    action_manager.sync_db()
    workflows.sync_db()


def do_populate_actions(config, cmd):
    LOG.info("Populating actions db")
    action_manager.sync_db()


def do_revision(config, cmd):
    do_alembic_command(
        config, cmd,
        message=CONF.command.message,
        autogenerate=CONF.command.autogenerate,
        sql=CONF.command.sql,
        rev_id=CONF.command.rev_id
    )


def add_command_parsers(subparsers):
    for name in ['current', 'history', 'branches']:
        parser = subparsers.add_parser(name)
        parser.set_defaults(func=do_alembic_command)

    parser = subparsers.add_parser('upgrade')
    parser.add_argument('--delta', type=int)
    parser.add_argument('--sql', action='store_true')
    parser.add_argument('revision', nargs='?')
    parser.set_defaults(func=do_upgrade)

    parser = subparsers.add_parser('populate')
    parser.set_defaults(func=do_populate)

    parser = subparsers.add_parser('populate_actions')
    parser.set_defaults(func=do_populate_actions)

    parser = subparsers.add_parser('stamp')
    parser.add_argument('--sql', action='store_true')
    parser.add_argument('revision', nargs='?')
    parser.set_defaults(func=do_stamp)

    parser = subparsers.add_parser('revision')
    parser.add_argument('-m', '--message')
    parser.add_argument('--rev-id', dest='rev_id')
    parser.add_argument('--autogenerate', action='store_true')
    parser.add_argument('--sql', action='store_true')
    parser.set_defaults(func=do_revision)


command_opt = cfg.SubCommandOpt('command',
                                title='Command',
                                help='Available commands',
                                handler=add_command_parsers)

CONF.register_cli_opt(command_opt)

# To Keep backwards compatibility we need to accept mapping path
# from mistral-extra if present
try:
    import mistral_extra.config as extra_conf
    CONF.register_cli_opt(extra_conf.os_actions_mapping_path)
except ImportError:
    LOG.debug("Mistral-extra not installed")


def main():
    config = alembic_cfg.Config(
        os.path.join(os.path.dirname(__file__), 'alembic.ini')
    )
    config.set_main_option(
        'script_location',
        'mistral.db.sqlalchemy.migration:alembic_migrations'
    )
    # attach the Mistral conf to the Alembic conf
    config.mistral_config = CONF
    logging.register_options(CONF)

    CONF(project='mistral')
    logging.setup(CONF, 'Mistral')
    CONF.command.func(config, CONF.command.name)


if __name__ == '__main__':
    sys.exit(main())
