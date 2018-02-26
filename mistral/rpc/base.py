# Copyright 2015 - Mirantis, Inc.
# Copyright 2017 - Brocade Communications Systems, Inc.
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

import abc

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_messaging.rpc import client
from stevedore import driver

from mistral import exceptions as exc


LOG = logging.getLogger(__name__)


_IMPL_CLIENT = None
_IMPL_SERVER = None
_TRANSPORT = None


def cleanup():
    """Intended to be used by tests to recreate all RPC related objects."""

    global _TRANSPORT

    _TRANSPORT = None


# TODO(rakhmerov): This method seems misplaced. Now we have different kind
# of transports (oslo, kombu) and this module should not have any oslo
# specific things anymore.
def get_transport():
    global _TRANSPORT

    if not _TRANSPORT:
        _TRANSPORT = messaging.get_rpc_transport(cfg.CONF)

    return _TRANSPORT


def get_rpc_server_driver():
    rpc_impl = cfg.CONF.rpc_implementation

    global _IMPL_SERVER
    if not _IMPL_SERVER:
        _IMPL_SERVER = driver.DriverManager(
            'mistral.rpc.backends',
            '%s_server' % rpc_impl
        ).driver

    return _IMPL_SERVER


def get_rpc_client_driver():
    rpc_impl = cfg.CONF.rpc_implementation

    global _IMPL_CLIENT
    if not _IMPL_CLIENT:
        _IMPL_CLIENT = driver.DriverManager(
            'mistral.rpc.backends',
            '%s_client' % rpc_impl
        ).driver

    return _IMPL_CLIENT


def _wrap_exception_and_reraise(exception):
    message = "%s: %s" % (exception.__class__.__name__, exception.args[0])

    raise exc.MistralException(message)


def wrap_messaging_exception(method):
    """The decorator unwraps a remote error into one of the mistral exceptions.

    oslo.messaging has different behavior on raising exceptions depending on
    whether we use 'fake' or 'rabbit' transports. In case of 'rabbit' transport
    it raises an instance of RemoteError which forwards directly to the API.
    The RemoteError instance contains one of the MistralException instances
    raised remotely on the RPC server side and for correct exception handling
    we need to unwrap and raise the original wrapped exception.
    """
    def decorator(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except exc.MistralException:
            raise
        except (client.RemoteError, exc.KombuException, Exception) as e:
            # Since we're going to transform the original exception
            # we need to log it as is.
            LOG.exception(
                "Caught a messaging remote error."
                " See details of the original exception."
            )

            if hasattr(e, 'exc_type') and hasattr(exc, e.exc_type):
                exc_cls = getattr(exc, e.exc_type)

                raise exc_cls(e.value)

            _wrap_exception_and_reraise(e)

    return decorator


class RPCClient(object):
    def __init__(self, conf):
        """Base class for RPCClient's drivers

        RPC Client is responsible for sending requests to RPC Server.
        All RPC client drivers have to inherit from this class.

        :param conf: Additional config provided by upper layer.
        """
        self.conf = conf

    @abc.abstractmethod
    def sync_call(self, ctx, method, target=None, **kwargs):
        """Synchronous call of RPC method.

        Blocks the thread and wait for method result.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def async_call(self, ctx, method, target=None, fanout=False, **kwargs):
        """Asynchronous call of RPC method.

        Does not block the thread, just send invoking data to
        the RPC server and immediately returns nothing.
        """
        raise NotImplementedError


class RPCServer(object):
    def __init__(self, conf):
        """Base class for RPCServer's drivers

        RPC Server should listen for request coming from RPC Clients and
        respond to them respectively to the registered endpoints.
        All RPC server drivers have to inherit from this class.

        :param conf: Additional config provided by upper layer.
        """
        self.conf = conf

    @abc.abstractmethod
    def register_endpoint(self, endpoint):
        """Registers a new RPC endpoint.

        :param endpoint: an object containing methods which
         will be used as RPC methods.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run(self, executor='eventlet'):
        """Runs the RPC server.

        :param executor: Executor used to process incoming requests. Different
            implementations may support different options.
        """
        raise NotImplementedError

    def stop(self, graceful=False):
        """Stop the RPC server.

        :param graceful: True if this method call should wait till all
            internal threads are finished.
        :return:
        """
        # No-op by default.
        pass

    def wait(self):
        """Wait till all internal threads are finished."""
        # No-op by default.
        pass
