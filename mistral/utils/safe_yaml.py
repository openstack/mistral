#  Copyright 2019 - Nokia Corporation
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import yaml
from yaml import *  # noqa

yaml.SafeDumper.ignore_aliases = lambda *args: True


class SafeLoader(yaml.SafeLoader):
    """Treat '@', '&', '*' as plain string.

       Anchors are not used in mistral workflow. It's better to
       disable them completely. Anchors can be used as an exploit to a
       Denial of service attack through expansion (Billion Laughs)
       see https://en.wikipedia.org/wiki/Billion_laughs_attack.
       Also this module uses the safe loader by default which is always
       a better loader.

       When using yaml module to load a yaml file or a string use this
       module instead of yaml.

       Example:
         import mistral.utils.safe_yaml as safe_yaml
         ...
         ...

         safe_yaml.load(...)

    """

    def fetch_alias(self):
        return self.fetch_plain()

    def fetch_anchor(self):
        return self.fetch_plain()

    def check_plain(self):
        # Modified: allow '@'
        if self.peek() == '@':
            return True
        else:
            return super(SafeLoader, self).check_plain()


def load(stream):
    return yaml.load(stream, SafeLoader)


def safe_load(stream):
    return load(stream)
