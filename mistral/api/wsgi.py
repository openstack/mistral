# Copyright 2015 - StackStorm, Inc.
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

from mistral.api import app
from mistral import config

# By default, oslo.config parses the CLI args if no args is provided.
# As a result, invoking this wsgi script from gunicorn leads to the error
# with argparse complaining that the CLI options have already been parsed.
config.parse_args(args=[])

application = app.setup_app()
