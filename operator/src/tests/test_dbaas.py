"""
Unit tests for DBaaSHelper
"""

import pytest
import requests
from unittest.mock import MagicMock, patch

from dbaas_helper import DBaaSHelper

NAMESPACE = "test-ns"
BASE_URL = "http://dbaas-aggregator:8080"


@pytest.fixture
def helper():
    return DBaaSHelper(BASE_URL + "/", "user", "pw", NAMESPACE)


def _resp(status_code, json_data=None, raise_err=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.text = str(json_data)
    r.raise_for_status.side_effect = raise_err
    return r


def test_trailing_slash_stripped():
    h = DBaaSHelper(BASE_URL + "/", "u", "p", NAMESPACE)
    assert h._base == BASE_URL


@patch('dbaas_helper.requests.post')
def test_get_by_classifier_returns_none_on_404(mock_post, helper):
    mock_post.return_value = _resp(404)
    assert helper.get_by_classifier() is None


@patch('dbaas_helper.requests.post')
def test_get_by_classifier_returns_json_on_200(mock_post, helper):
    payload = {'connectionProperties': {'host': 'pg', 'port': 5432}}
    mock_post.return_value = _resp(200, payload)
    assert helper.get_by_classifier() == payload


@patch('dbaas_helper.requests.post')
def test_get_by_classifier_raises_on_5xx(mock_post, helper):
    mock_post.return_value = _resp(500, raise_err=requests.HTTPError("500"))
    with pytest.raises(requests.HTTPError):
        helper.get_by_classifier()


@patch('dbaas_helper.requests.post')
def test_get_by_classifier_uses_correct_url_and_auth(mock_post, helper):
    mock_post.return_value = _resp(200, {})
    helper.get_by_classifier()
    url = mock_post.call_args[0][0]
    assert f"/api/v3/dbaas/{NAMESPACE}/databases/get-by-classifier/postgresql" in url
    assert mock_post.call_args[1]['auth'] == ("user", "pw")


@patch('dbaas_helper.requests.put')
def test_create_db_returns_json_on_201(mock_put, helper):
    payload = {'connectionProperties': {'host': 'new-pg'}}
    mock_put.return_value = _resp(201, payload)
    assert helper.create_db() == payload


@patch('dbaas_helper.requests.put')
def test_create_db_raises_on_error(mock_put, helper):
    mock_put.return_value = _resp(409, raise_err=requests.HTTPError("409"))
    with pytest.raises(requests.HTTPError):
        helper.create_db()

@patch('dbaas_helper.requests.put')
def test_register_external_db_sends_full_connection_details(mock_put, helper):
    mock_put.return_value = _resp(200, {})
    helper.register_external_db('my-pg', 5432, 'mistral', 'db_user', 'db_pw')

    body = mock_put.call_args[1]['json']
    cp = body['connectionProperties'][0]

    assert cp['host'] == 'my-pg'
    assert cp['port'] == '5432'
    assert cp['name'] == 'mistral'
    assert cp['username'] == 'db_user'
    assert cp['password'] == 'db_pw'
    assert body['type'] == 'postgresql'
    assert body['classifier']['microserviceName'] == 'mistral-operator'
    assert body['classifier']['namespace'] == NAMESPACE


@patch('dbaas_helper.requests.put')
def test_migrate_external_sends_list_with_classifier(mock_put, helper):
    mock_put.return_value = _resp(200)
    helper.migrate_external_to_internal('pg', 5432, 'db', 'u', 'pw')
    body = mock_put.call_args[1]['json']
    assert isinstance(body, list) and len(body) == 1
    assert body[0]['namespace'] == NAMESPACE
    assert body[0]['classifier']['microserviceName'] == 'mistral-operator'


@patch('dbaas_helper.requests.put')
def test_migrate_external_raises_on_error(mock_put, helper):
    mock_put.return_value = _resp(500, raise_err=requests.HTTPError("500"))
    with pytest.raises(requests.HTTPError):
        helper.migrate_external_to_internal('pg', 5432, 'db', 'u', 'pw')
