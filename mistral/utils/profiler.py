# Copyright 2016 - Brocade Communications Systems, Inc.
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

import copy
import datetime
import json

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils
import osprofiler.profiler
import osprofiler.web

from mistral_lib import utils


PROFILER_LOG = logging.getLogger(cfg.CONF.profiler.profiler_log_name)


def log_to_file(info, context=None):
    attrs = [
        str(info['timestamp']),
        info['base_id'],
        info['parent_id'],
        info['trace_id'],
        info['name']
    ]

    th_local_name = '_profiler_trace_%s_start_time_' % info['trace_id']

    if info['name'].endswith('-start'):
        utils.set_thread_local(th_local_name, timeutils.utcnow())

        # Insert a blank sequence for a trace start.
        attrs.insert(1, ' ' * 8)

    if info['name'].endswith('-stop'):
        delta = (
            timeutils.utcnow() - utils.get_thread_local(th_local_name)
        ).total_seconds()

        utils.set_thread_local(th_local_name, None)

        # Insert a blank sequence for a trace start.
        attrs.insert(1, str(delta))

        if delta > 0.5:
            attrs.append(' <- !!!')

    if 'info' in info and 'db' in info['info']:
        db_info = copy.deepcopy(info['info']['db'])

        db_info['params'] = {
            k: str(v) if isinstance(v, datetime.datetime) else v
            for k, v in db_info.get('params', {}).items()
        }

        attrs.append(json.dumps(db_info))

    PROFILER_LOG.info(' '.join(attrs))


def setup(binary, host):
    if cfg.CONF.profiler.enabled:
        osprofiler.notifier.set(log_to_file)
        osprofiler.web.enable(cfg.CONF.profiler.hmac_keys)
