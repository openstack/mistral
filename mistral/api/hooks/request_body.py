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

import pecan
from pecan import hooks

# Media types that route to an XML parser. Mistral's API only consumes
# JSON (and raw YAML for the definition endpoints); XML is not supported.
# Parsing untrusted XML exposes the service to entity-expansion attacks
# because wsme deserializes XML bodies with a bare
# xml.etree.ElementTree.fromstring() (see wsme.rest.xml.parse), which
# runs before any authorization or schema validation.
_XML_CONTENT_TYPES = ('text/xml', 'application/xml')


def _is_xml_content_type(content_type):
    if not content_type:
        return False

    content_type = content_type.lower()

    return content_type in _XML_CONTENT_TYPES or content_type.endswith('+xml')


class RejectXMLHook(hooks.PecanHook):
    """Rejects request bodies with an unsupported (XML) content type."""

    def before(self, state):
        # 'content_type' is the media type without its parameters
        # (e.g. the charset), so it can be matched directly.
        if _is_xml_content_type(state.request.content_type):
            msg = "XML request bodies are not supported."

            pecan.abort(
                status_code=415,
                detail=msg,
                headers={'Server-Error-Message': msg}
            )
