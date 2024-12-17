# This file is part of Flask-Multipass-Keycloak.
# Copyright (C) 2023 - 2024 CERN & UNCONVENTIONAL

from datetime import datetime

import freezegun
import pytest
from flask import Flask
from flask_multipass import Multipass
from requests import Session

from flask_multipass_keycloak import KeycloakIdentityProvider


class MemoryCacheEntry:
    def __init__(self, value, timeout=0):
        self.value = value
        self.timeout = timeout if timeout else None
        self.timestamp = datetime.now()


class MemoryCache:
    """Simple dict-based in memory cache with expiration."""

    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        entry = self.data.get(key, default)

        if entry is None or not isinstance(entry, MemoryCacheEntry):
            return default
        elif entry.timeout:
            if (datetime.now() - entry.timestamp).total_seconds() >= entry.timeout:
                del self.data[key]
                return default
        return entry.value

    def set(self, key, value, timeout=0):
        self.data[key] = MemoryCacheEntry(value, timeout)


@pytest.fixture(autouse=True)
def flask_app():
    app = Flask(__name__)
    Multipass(app)
    with app.app_context():
        yield app


@pytest.fixture
def provider():
    settings = {
        'identifier_field': 'email',
        'keycloak_args': {
            'grant_type': 'client_credentials',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'access_token_url': 'http://localhost/realms/test_realm/protocol/openid-connect/token',
            'realm_api_url': 'http://localhost/admin/realms/test_realm'
        },
        'cache': MemoryCache
    }
    return KeycloakIdentityProvider(None, 'kcip', settings)


@pytest.fixture
def freeze_time():
    freezers = []

    def _freeze_time(time_to_freeze):
        freezer = freezegun.freeze_time(time_to_freeze)
        freezer.start()
        freezers.append(freezer)

    yield _freeze_time
    for freezer in reversed(freezers):
        freezer.stop()


@pytest.fixture
def mock_get_api_session(mocker):
    get_api_session = mocker.patch('flask_multipass_keycloak.KeycloakIdentityProvider._get_api_session')
    get_api_session.return_value = Session()
    return get_api_session
