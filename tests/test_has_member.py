# This file is part of Flask-Multipass-Keycloak.
# Copyright (C) 2023 - 2024 CERN

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from requests import Session
from requests.exceptions import RequestException

from flask_multipass_keycloak import KeycloakGroup
from tests.conftest import MemoryCache


@pytest.fixture
def mock_get_api_session(mocker):
    get_api_session = mocker.patch('flask_multipass_keycloak.KeycloakIdentityProvider._get_api_session')
    get_api_session.return_value = Session()
    return get_api_session


@pytest.fixture
def mock_get_identity_groups(mocker):
    get_identity_groups = mocker.patch('flask_multipass_keycloak.KeycloakIdentityProvider.get_identity_groups')
    group = MagicMock()
    group.name = 'keycloak group'
    get_identity_groups.return_value = {group}
    return get_identity_groups


@pytest.fixture
def mock_get_identity_groups_fail(mocker):
    get_identity_groups = mocker.patch('flask_multipass_keycloak.KeycloakIdentityProvider.get_identity_groups')
    get_identity_groups.side_effect = RequestException()
    return get_identity_groups


@pytest.fixture
def spy_cache_set(mocker):
    return mocker.spy(MemoryCache, 'set')


@pytest.mark.usefixtures('mock_get_identity_groups')
def test_has_member_cache(provider):
    test_group = KeycloakGroup(provider, 'keycloak group')
    test_group.has_member('12345')

    assert test_group.provider.cache.get('flask-multipass-keycloak:kcip:groups:12345')
    assert test_group.provider.cache.get('flask-multipass-keycloak:kcip:groups:12345:timestamp')


@pytest.mark.usefixtures('mock_get_identity_groups')
def test_has_member_cache_miss(provider, spy_cache_set):
    test_group = KeycloakGroup(provider, 'keycloak group')
    test_group.has_member('12345')

    assert spy_cache_set.call_count == 2


def test_has_member_cache_hit(provider, mock_get_identity_groups):
    test_group = KeycloakGroup(provider, 'keycloak group')
    test_group.provider.cache.set('flask-multipass-keycloak:kcip:groups:12345', 'keycloak group')
    test_group.provider.cache.set('flask-multipass-keycloak:kcip:groups:12345:timestamp', datetime.now())
    test_group.has_member('12345')

    assert not mock_get_identity_groups.called


@pytest.mark.usefixtures('mock_get_identity_groups')
def test_has_member_request_fails(provider, mock_get_identity_groups_fail):
    test_group = KeycloakGroup(provider, 'keycloak group')
    res = test_group.has_member('12345')

    assert mock_get_identity_groups_fail.called
    assert res is False
