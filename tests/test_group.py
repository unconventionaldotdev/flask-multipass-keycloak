# This file is part of Flask-Multipass-Keycloak.
# Copyright (C) 2023 - 2024 CERN

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from flask_multipass.data import IdentityInfo
from requests.exceptions import RequestException

from flask_multipass_keycloak import KeycloakGroup
from tests.conftest import MemoryCache


@pytest.fixture
def mock_get_identity_groups(mocker):
    get_identity_groups = mocker.patch('flask_multipass_keycloak.KeycloakIdentityProvider.get_identity_groups')
    group = MagicMock()
    group.name = 'keycloak group'
    get_identity_groups.return_value = {group}
    return get_identity_groups


@pytest.fixture
def mock_api_get_group(mocker):
    get_group_data = mocker.patch('flask_multipass_keycloak.KeycloakIdentityProvider._get_group_data')
    get_group_data.return_value = {'id': 'group-id-1',
                                   'name': 'group-name-1',
                                   'path': 'group/path/group-name-1'}
    return get_group_data


@pytest.fixture
def mock_api_get_group_members(mocker):
    get_group_members = mocker.patch('flask_multipass_keycloak.KeycloakIdentityProvider._fetch_all')
    get_group_members.return_value = [{'email': 'john.doe@mail.com', 'firstName': 'John', 'lastName': 'Doe'},
                                      {'email': 'jane.doe@mail.com', 'firstName': 'Jane', 'lastName': 'Doe'}]
    return get_group_members


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

    assert test_group.has_member('12345') is True
    assert test_group.provider.cache.get('flask-multipass-keycloak:kcip:groups:12345')
    assert test_group.provider.cache.get('flask-multipass-keycloak:kcip:groups:12345:timestamp')


@pytest.mark.usefixtures('mock_get_identity_groups')
def test_has_member_cache_miss(provider, spy_cache_set):
    test_group = KeycloakGroup(provider, 'keycloak group')

    assert test_group.has_member('12345') is True
    assert spy_cache_set.call_count == 2


def test_has_member_cache_hit(provider, mock_get_identity_groups):
    test_group = KeycloakGroup(provider, 'keycloak group')
    test_group.provider.cache.set('flask-multipass-keycloak:kcip:groups:12345', 'keycloak group')
    test_group.provider.cache.set('flask-multipass-keycloak:kcip:groups:12345:timestamp', datetime.now())

    assert test_group.has_member('12345') is True
    assert not mock_get_identity_groups.called


@pytest.mark.usefixtures('mock_get_identity_groups')
def test_has_member_request_fails(provider, mock_get_identity_groups_fail):
    test_group = KeycloakGroup(provider, 'keycloak group')

    assert test_group.has_member('12345') is False
    assert mock_get_identity_groups_fail.called


@pytest.mark.usefixtures('mock_get_api_session', 'mock_api_get_group', 'mock_api_get_group_members')
def test_get_members(provider):
    test_group = KeycloakGroup(provider, 'keycloak group')
    members = list(test_group.get_members())

    assert len(members) == 2
    assert all(isinstance(member, IdentityInfo) for member in members)
