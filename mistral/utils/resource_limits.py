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

import resource

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def apply_memory_limit(limit_mb):
    """Apply a soft address-space (memory) limit to the current process.

    A *soft* RLIMIT_AS is used on purpose: when the process tries to
    allocate more than the limit, the allocation raises MemoryError
    instead of the kernel killing the process with SIGKILL (as a hard
    limit would). This lets Mistral turn a runaway allocation - for
    instance a workflow expression such as ``{{ [0] * 2000000000 }}`` -
    into a catchable error that fails a single evaluation rather than
    exhausting the host memory and taking the whole service down.

    :param limit_mb: The limit in mebibytes. Values <= 0 disable it.
    """

    if not limit_mb or limit_mb <= 0:
        return

    limit_bytes = limit_mb * 1024 * 1024

    soft, hard = resource.getrlimit(resource.RLIMIT_AS)

    # Never raise the existing hard limit (that would require privileges
    # anyway) and keep the soft limit below it.
    new_soft = limit_bytes

    if hard != resource.RLIM_INFINITY:
        new_soft = min(new_soft, hard)

    resource.setrlimit(resource.RLIMIT_AS, (new_soft, hard))

    LOG.info(
        "Applied a soft address-space limit of %d MiB to the process.",
        new_soft // (1024 * 1024)
    )
