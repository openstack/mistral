# Copyright 2020 Nokia Software.
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


from oslo_log import log as logging

from mistral.db.v2 import api as db_api

LOG = logging.getLogger(__name__)

_SYSTEM_PROVIDER = None
_TEST_PROVIDER = None


def create_code_source(name, src_code, namespace='', version=1):
    with db_api.transaction():
        return db_api.create_code_source({
            'name': name,
            'namespace': namespace,
            'version': version,
            'src': src_code,
        })


def create_code_sources(namespace='', **files):
    return _update_or_create_code_sources(
        create_code_source,
        namespace,
        **files
    )


def _update_or_create_code_sources(operation, namespace='', **files):
    code_sources = []

    for file in files:
        filename = files[file].name
        file_content = files[file].file.read().decode()

        code_sources.append(
            operation(
                filename,
                file_content,
                namespace
            )
        )

    return code_sources


def update_code_sources(namespace='', **files):
    return _update_or_create_code_sources(
        update_code_source,
        namespace,
        **files
    )


def update_code_source(identifier, src_code, namespace=''):
    with db_api.transaction():
        return db_api.update_code_source(
            identifier=identifier,
            namespace=namespace,
            values={'src': src_code}
        )


def delete_code_source(identifier, namespace=''):
    with db_api.transaction():
        db_api.delete_code_source(identifier, namespace=namespace)


def delete_code_sources(code_sources, namespace=''):
    with db_api.transaction():
        for code_source in code_sources:
            db_api.delete_code_source(code_source, namespace=namespace)


def get_code_source(identifier, namespace='', fields=()):
    return db_api.get_code_source(
        identifier,
        namespace=namespace,
        fields=fields
    )
