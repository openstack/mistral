# Copyright 2026 - NetCracker Technology Corp.
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

import json
import re

from oslo_config import cfg
from oslo_log import log as logging


LOG = logging.getLogger(__name__)

CONF = cfg.CONF

RULE_TYPE_EXTRACT = 'extract'
RULE_TYPE_MAP = 'map'


_FIELD_INDEX_RE = re.compile(r'^(.+)\[(\d+)\]$')


def _resolve_field_value(decoded_token, field):
    """Return the claim value for field, supporting index notation (e.g. aud[0])."""
    match = _FIELD_INDEX_RE.match(field)
    if match:
        field_name, index = match.group(1), int(match.group(2))
        claim = decoded_token.get(field_name)
        if not isinstance(claim, list):
            LOG.warning(
                "Field %r is not a list in token but index notation was used.",
                field_name
            )
            return None
        if index >= len(claim):
            LOG.warning(
                "Index %d is out of range for field %r (length %d).",
                index, field_name, len(claim)
            )
            return None
        return claim[index]

    return decoded_token.get(field)


def _pattern_to_regex(pattern):
    token_re = re.compile(r'(\*|\{value\})')
    parts = token_re.split(pattern)
    regex_parts = []
    for part in parts:
        if part == '*':
            regex_parts.append('.*')
        elif part == '{value}':
            regex_parts.append('(?P<value>[^/]+)')
        else:
            regex_parts.append(re.escape(part))
    return re.compile('^' + ''.join(regex_parts) + '$')


def resolve_project_id(decoded_token, rules):
    """Evaluate project rules in order, return first matched project_id or None."""
    for rule in rules:
        rule_type = rule.get('type')
        field = rule.get('field')
        pattern = rule.get('pattern')

        if not field:
            LOG.warning(
                "Skipping invalid project rule (missing field): %s", rule
            )
            continue

        if rule_type == RULE_TYPE_EXTRACT and not pattern:
            LOG.warning(
                "Skipping 'extract' rule missing required pattern: %s", rule
            )
            continue

        field_value = _resolve_field_value(decoded_token, field)
        if field_value is None:
            continue

        if rule_type == RULE_TYPE_EXTRACT:
            try:
                compiled = _pattern_to_regex(pattern)
            except re.error:
                LOG.warning(
                    "Skipping project rule with invalid pattern %r: %s",
                    pattern, rule
                )
                continue

            match = compiled.match(str(field_value))
            if not match:
                continue

            return match.group('value')

        if rule_type == RULE_TYPE_MAP:
            expected_value = rule.get('value')
            project = rule.get('project')
            if not expected_value or not project:
                LOG.warning(
                    "Skipping 'map' rule missing 'value' or 'project': %s",
                    rule
                )
                continue

            if pattern:
                try:
                    compiled = _pattern_to_regex(pattern)
                except re.error:
                    LOG.warning(
                        "Skipping project rule with invalid pattern %r: %s",
                        pattern, rule
                    )
                    continue

                match = compiled.match(str(field_value))
                if not match:
                    continue
                candidate = match.group('value')
            else:
                candidate = str(field_value)

            if candidate == str(expected_value):
                return project

        else:
            LOG.warning(
                "Skipping project rule with unknown type %r: %s",
                rule_type, rule
            )

    return None


def resolve_project_id_from_config(decoded_token):
    """Resolve project_id from CONF.auth.project_rules; returns None if unset or no match."""
    raw_rules = CONF.auth.project_rules
    if not raw_rules:
        return None

    try:
        rules = json.loads(raw_rules)
    except (ValueError, TypeError):
        LOG.warning(
            "Failed to parse auth.project_rules config as JSON; "
            "project_id resolution via rules will be skipped."
        )
        return None

    return resolve_project_id(decoded_token, rules)
