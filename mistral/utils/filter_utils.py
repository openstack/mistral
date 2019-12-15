#    Copyright 2016 NEC Corporation.  All rights reserved.
#    Copyright 2019 Nokia Software.  All rights reserved.
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

EQUALS = 'eq'
NOT_EQUAL = 'neq'
LESS_THAN = 'lt'
LESS_THAN_EQUALS = 'lte'
GREATER_THAN = 'gt'
GREATER_THAN_EQUALS = 'gte'
IN = 'in'
NOT_IN = 'nin'
HAS = 'has'

ALL = (GREATER_THAN_EQUALS, GREATER_THAN,
       LESS_THAN_EQUALS, HAS, NOT_EQUAL,
       LESS_THAN, IN, EQUALS, NOT_IN)


def create_filters_from_request_params(none_values=None, **params):
    """Create filters from REST request parameters.

    :param none_values: field names, where the value is required to be None.
    :param req_params: REST request parameters.
    :return: filters dictionary.
    """
    none_values = none_values or []
    filters = {}

    for column, data in params.items():
        if (data is None and column in none_values) or data is not None:
            if isinstance(data, six.string_types):
                f_type, value = extract_filter_type_and_value(data)

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
    :param _filter: Optional. If provided same filter dictionary will
                    be updated.
    :return: filter dictionary.

    """
    if _filter is None:
        _filter = {}

    _filter[column] = {filter_type: value}

    return _filter


def extract_filter_type_and_value(data):
    """Extract filter type and its value from the data.

    :param data: REST parameter value from which filter type and
                 value can be get. It should be in format of
                 'filter_type:value'.
    :return: filter type and value.
    """
    if has_filters(data):
        filter_type, value = data.split(':', 1)
        value = six.text_type(value)
        if data.startswith((IN, NOT_IN)):
            value = list(value.split(","))
    else:
        value = data
        filter_type = EQUALS

    return filter_type, value


def has_filters(value):
    for filter_type in ALL:
        if value.startswith(filter_type + ':'):
            return True
    return False
