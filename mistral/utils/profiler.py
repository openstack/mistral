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
import six

from oslo_config import cfg
from oslo_log import log as logging
import osprofiler.profiler
import osprofiler.web


PROFILER_LOG = logging.getLogger(cfg.CONF.profiler.profiler_log_name)


def log_to_file(info, context=None):
    attrs = [
        str(info['timestamp']),
        info['base_id'],
        info['parent_id'],
        info['trace_id'],
        info['name']
    ]

    if 'info' in info and 'db' in info['info']:
        db_info = copy.deepcopy(info['info']['db'])

        db_info['params'] = {
            k: str(v) if isinstance(v, datetime.datetime) else v
            for k, v in six.iteritems(db_info.get('params', {}))
        }

        attrs.append(json.dumps(db_info))

    PROFILER_LOG.info(' '.join(attrs))


def setup(binary, host):
    if cfg.CONF.profiler.enabled:
        osprofiler.notifier.set(log_to_file)
        osprofiler.web.enable(cfg.CONF.profiler.hmac_keys)
