# Copyright 2013 - Mirantis, Inc.
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

"""Access Control API server."""

from keystonemiddleware import auth_token
from oslo_config import cfg
from oslo_policy import policy

from mistral import exceptions as exc
from mistral import policies


CONF = cfg.CONF

_ENFORCER = None


def setup(app):
    if cfg.CONF.pecan.auth_enable and cfg.CONF.auth_type == 'keystone':
        conf = dict(cfg.CONF.keystone_authtoken)

        # Change auth decisions of requests to the app itself.
        conf.update({'delay_auth_decision': True})

        # NOTE(rakhmerov): Policy enforcement works only if Keystone
        # authentication is enabled. No support for other authentication
        # types at this point.
        _ensure_enforcer_initialization()

        return auth_token.AuthProtocol(app, conf)
    else:
        return app


def enforce(action, context, target=None, do_raise=True,
            exc=exc.NotAllowedException):
    """Verifies that the action is valid on the target in this context.

    :param action: String, representing the action to be checked.
                   This should be colon separated for clarity.
                   i.e. ``workflows:create``
    :param context: Mistral context.
    :param target: Dictionary, representing the object of the action.
                   For object creation, this should be a dictionary
                   representing the location of the object.
                   e.g. ``{'project_id': context.project_id}``
    :param do_raise: if True (the default), raises specified exception.
    :param exc: Exception to be raised if not authorized. Default is
                mistral.exceptions.NotAllowedException.

    :return: returns True if authorized and False if not authorized and
             do_raise is False.
    """

    target_obj = {
        'project_id': context.project_id,
        'user_id': context.user_id,
    }
    target_obj.update(target or {})

    policy_context = context.to_policy_values()
    # Because policy.json or policy.yaml example in Mistral repo still uses
    # the rule 'is_admin: True', we insert 'is_admin' key to the default
    # policy values.
    policy_context['is_admin'] = context.is_admin

    _ensure_enforcer_initialization()

    return _ENFORCER.authorize(
        action,
        target_obj,
        policy_context,
        do_raise=do_raise,
        exc=exc
    )


def get_enforcer():
    """Entrypoint that must return the raw oslo.policy enforcer obj.

    This is utilized by the command-line policy tools.

    :returns: :class:`oslo_policy.policy.Enforcer`
    """
    # Here we pass an empty list of arguments because there aren't any
    # arguments that oslo.config or oslo.policy shouldn't already understand
    # from the CONF object. This makes things easier here because we don't have
    # to parse arguments passed in from the command line and remove unexpected
    # arguments before building a Config object.
    CONF([], project='mistral')
    enforcer = policy.Enforcer(CONF)
    enforcer.register_defaults(policies.list_rules())
    enforcer.load_rules()

    return enforcer


def _ensure_enforcer_initialization():
    global _ENFORCER
    if not _ENFORCER:
        _ENFORCER = policy.Enforcer(cfg.CONF)
        _ENFORCER.register_defaults(policies.list_rules())
        _ENFORCER.load_rules()


def get_limited_to(headers):
    """Return the user and project the request should be limited to.

    :param headers: HTTP headers dictionary
    :return: A tuple of (user, project), set to None if there's no limit on
    one of these.

    """
    return headers.get('X-User-Id'), headers.get('X-Project-Id')


def get_limited_to_project(headers):
    """Return the project the request should be limited to.

    :param headers: HTTP headers dictionary
    :return: A project, or None if there's no limit on it.

    """
    return get_limited_to(headers)[1]
