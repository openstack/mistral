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

import re

MASK = '***'

# Keys whose value is considered sensitive and must never be logged.
_SENSITIVE_KEY_RE = re.compile(
    r'(passwd|password|token|secret|auth|api[_-]?key|apikey|credential|'
    r'cookie|private_key)',
    re.IGNORECASE
)


def redact_sensitive(data):
    """Return a copy of data with sensitive-looking values masked.

    Recursively walks dicts and lists. The value of any dict key whose
    name matches a sensitive pattern (password, token, secret, auth,
    api_key, credential, cookie, private_key, ...) is replaced with
    ``***``. This is meant to sanitize arbitrary user-supplied data
    (workflow inputs, environments, HTTP params, notification publisher
    configs, ...) before it is written to the logs.
    """

    if isinstance(data, dict):
        redacted = {}

        for key, value in data.items():
            if isinstance(key, str) and _SENSITIVE_KEY_RE.search(key):
                redacted[key] = MASK
            else:
                redacted[key] = redact_sensitive(value)

        return redacted

    if isinstance(data, list):
        return [redact_sensitive(v) for v in data]

    if isinstance(data, tuple):
        return tuple(redact_sensitive(v) for v in data)

    return data
