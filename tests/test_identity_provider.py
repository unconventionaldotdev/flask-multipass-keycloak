# This file is part of Flask-Multipass-Keycloak.
# Copyright (C) 2023 - 2024 CERN

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from requests.exceptions import RequestException

from flask_multipass.data import IdentityInfo
from flask_multipass_keycloak import KeycloakGroup
from tests.conftest import MemoryCache


@pytest.fixture
def mock_api_get_groups(mocker):
    get_groups = mocker.patch('flask_multipass_keycloak.KeycloakIdentityProvider._fetch_all')
    get_groups.return_value = [{'name': 'group-1', 'path': '/root/group-1'},
                               {'name': 'group-2', 'path': '/root/level-1/group-2'}]
    return get_groups


def test_group_path_as_name(provider):
    assert provider.group_path_as_name('/root/level-1/level-2/Group Name') == 'root > level-1 > level-2 > Group Name'


def test_group_name_as_path(provider):
    assert provider.group_name_as_path('root > level-1 > level-2 > Group Name') == '/root/level-1/level-2/Group Name'


@pytest.mark.usefixtures('mock_get_api_session', 'mock_api_get_groups')
def test_search_groups(provider):
    groups = list(provider.search_groups('search-pattern'))

    assert len(groups) == 2
    assert all(isinstance(group, KeycloakGroup) for group in groups)
