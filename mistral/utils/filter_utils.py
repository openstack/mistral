#    Copyright 2016 NEC Corporation.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import six


def create_filters_from_request_params(**params):
    """Create filters from REST request parameters.

    :param req_params: REST request parameters.
    :return: filters dictionary.
    """
    filters = {}
    for column, data in six.iteritems(params):
        if data is not None:
            if isinstance(data, six.string_types):
                f_type, value = _extract_filter_type_and_value(data)
                create_or_update_filter(column, value, f_type, filters)
            else:
                create_or_update_filter(column, data, _filter=filters)
    return filters


def create_or_update_filter(column, value, filter_type='eq', _filter=None):
    """Create or Update filter.

    :param column: Column name by which user want to filter.
    :param value: Column value.
    :param filter_type: filter type. Filter type can be
                        'eq', 'neq', 'gt', 'gte', 'lte', 'in',
                        'lt', 'nin'. Default is 'eq'.
    :parma _filter: Optional. If provided same filter dictionary will
                    be updated.
    :return: filter dictionary.

    """
    if _filter is None:
        _filter = {}
    _filter[column] = {filter_type: value}

    return _filter


def _extract_filter_type_and_value(data):
    """Extract filter type and its value from the data.

    :param data: REST parameter value from which filter type and
                 value can be get. It should be in format of
                 'filter_type:value'.
    :return: filter type and value.
    """
    if data.startswith("in:"):
        value = list(six.text_type(data[3:]).split(","))
        filter_type = 'in'
    elif data.startswith("nin:"):
        value = list(six.text_type(data[4:]).split(","))
        filter_type = 'nin'
    elif data.startswith("neq:"):
        value = six.text_type(data[4:])
        filter_type = 'neq'
    elif data.startswith("gt:"):
        value = six.text_type(data[3:])
        filter_type = 'gt'
    elif data.startswith("gte:"):
        value = six.text_type(data[4:])
        filter_type = 'gte'
    elif data.startswith("lt:"):
        value = six.text_type(data[3:])
        filter_type = 'lt'
    elif data.startswith("lte:"):
        value = six.text_type(data[4:])
        filter_type = 'lte'
    elif data.startswith("eq:"):
        value = six.text_type(data[3:])
        filter_type = 'eq'
    else:
        value = data
        filter_type = 'eq'

    return filter_type, value
