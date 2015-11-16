# Copyright 2015 - StackStorm, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

import os

from oslo_config import cfg


def parse_args():
    # Look for .mistral.conf in the project directory by default.
    project_dir = '%s/../..' % os.path.dirname(__file__)
    config_file = '%s/.mistral.conf' % os.path.realpath(project_dir)
    config_files = [config_file] if os.path.isfile(config_file) else None
    cfg.CONF(args=[], default_config_files=config_files)
