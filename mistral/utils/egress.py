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

import ipaddress
import socket
from urllib import parse

from oslo_config import cfg
from oslo_log import log as logging

from mistral import exceptions as exc

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


def _denied_networks():
    # The whole deny-list is operator-controlled via
    # [action_std_http] denied_cidrs (which defaults to loopback and
    # link-local, so the cloud metadata service at 169.254.169.254 is
    # blocked out of the box). An operator can widen it (e.g. add RFC1918)
    # or narrow it - even to empty - to re-enable those targets.
    networks = []

    for cidr in CONF.action_std_http.denied_cidrs:
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            LOG.warning(
                "Ignoring invalid [action_std_http] denied_cidrs entry: %s",
                cidr
            )

    return networks


def validate_url(url):
    """Validate an outbound URL against the egress policy.

    Mitigates SSRF: rejects non-http(s) schemes and hosts that resolve to
    a blocked network (loopback / link-local by default - which covers the
    cloud metadata service - plus any operator-configured CIDR), and
    honors an optional [action_std_http] allowed_hosts allow-list.

    NOTE: this resolves the host and checks every returned address. There
    is a residual DNS-rebinding window between this check and the actual
    connection; operators needing stronger guarantees should also network
    isolate the executor from the metadata service and management
    endpoints.

    :raises exc.UrlNotAllowedException: if the URL is not permitted.
    """
    parsed = parse.urlsplit(url)

    if parsed.scheme not in ('http', 'https'):
        raise exc.UrlNotAllowedException(
            "URL scheme '%s' is not allowed (only http and https are)."
            % parsed.scheme
        )

    host = parsed.hostname

    if not host:
        raise exc.UrlNotAllowedException("URL does not contain a host.")

    allowed_hosts = CONF.action_std_http.allowed_hosts

    if allowed_hosts and host not in allowed_hosts:
        raise exc.UrlNotAllowedException(
            "Host '%s' is not in [action_std_http] allowed_hosts." % host
        )

    try:
        addr_infos = socket.getaddrinfo(host, parsed.port)
    except socket.gaierror:
        # If we cannot resolve the host, the request would fail to connect
        # anyway, so there is no SSRF to block here. Fail open to avoid
        # breaking name resolution differences between hosts.
        return

    denied = _denied_networks()

    for info in addr_infos:
        address = ipaddress.ip_address(info[4][0])

        for network in denied:
            if address in network:
                raise exc.UrlNotAllowedException(
                    "URL host '%s' resolves to a blocked address (%s)."
                    % (host, address)
                )
