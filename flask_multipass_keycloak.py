# This file is part of Flask-Multipass-Keycloak.
# Copyright (C) 2023 - 2024 CERN

import logging
from datetime import datetime
from functools import wraps
from importlib import import_module
from inspect import getcallargs
from urllib.parse import urljoin

import requests
from flask import current_app
from flask import g
from flask import has_request_context
from flask_multipass.data import IdentityInfo
from flask_multipass.group import Group
from flask_multipass.providers.authlib import AuthlibAuthProvider
from flask_multipass.providers.authlib import AuthlibIdentityProvider
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException

CACHE_LONG_TTL = 86400 * 7
CACHE_TTL = 1800


class ExtendedCache:
    def __init__(self, cache):
        self.cache = self._init_cache(cache)

    def _init_cache(self, cache):
        if cache is None:
            return None
        elif callable(cache):
            return cache()
        elif isinstance(cache, str):
            module_path, class_name = cache.rsplit('.', 1)
            module = import_module(module_path)
            return getattr(module, class_name)
        else:
            return cache

    def get(self, key, default=None):
        if self.cache is None:
            return default
        return self.cache.get(key, default)

    def set(self, key, value, timeout=0, refresh_timeout=None):
        if self.cache is None:
            return
        self.cache.set(key, value, timeout)
        if refresh_timeout:
            self.cache.set(f'{key}:timestamp', datetime.now(), refresh_timeout)

    def should_refresh(self, key):
        if self.cache is None:
            return True
        return self.cache.get(f'{key}:timestamp') is None


def memoize_request(f):
    @wraps(f)
    def memoizer(*args, **kwargs):
        if not has_request_context() or current_app.config['TESTING'] or current_app.config.get('REPL'):
            # No memoization outside request context
            return f(*args, **kwargs)

        try:
            cache = g._keycloack_multipass_memoize
        except AttributeError:
            g._keycloack_multipass_memoize = cache = {}

        key = (f.__module__, f.__name__, make_hashable(getcallargs(f, *args, **kwargs)))
        if key not in cache:
            cache[key] = f(*args, **kwargs)
        return cache[key]

    return memoizer


def make_hashable(obj):
    if isinstance(obj, (list, set)):
        return tuple(obj)
    elif isinstance(obj, dict):
        return frozenset((k, make_hashable(v)) for k, v in obj.items())
    return obj


class KeycloakAuthProvider(AuthlibAuthProvider):
    pass


class KeycloakGroup(Group):
    supports_member_list = True

    def get_members(self):
        group = self.provider._get_group_data(self.name)
        with self.provider._get_api_session() as api_session:
            url = urljoin(self.provider.keycloak_settings['realm_api_url'] + '/', f'groups/{group["id"]}/members')
            response = api_session.get(url)
            for member in response.json():
                yield IdentityInfo(self.provider,
                                   member['email'],
                                   first_name=member.get('firstName', ''),
                                   last_name=member.get('lastName', ''))

    def has_member(self, identifier):
        cache = self.provider.cache
        logger = self.provider.logger
        cache_key = f'flask-multipass-keycloak:{self.provider.name}:groups:{identifier}'
        all_groups = cache.get(cache_key)

        if all_groups is None or cache.should_refresh(cache_key):
            try:
                all_groups = {g.name.lower() for g in self.provider.get_identity_groups(identifier)}
                cache.set(cache_key, all_groups, CACHE_LONG_TTL, CACHE_TTL)
            except RequestException:
                logger.warning('Refreshing user groups failed for %s', identifier)
                if all_groups is None:
                    logger.error('Getting user groups failed for %s, access will be denied', identifier)
                    return False

        return self.name.lower() in all_groups


class KeycloakIdentityProvider(AuthlibIdentityProvider):
    supports_get_identity_groups = True
    supports_groups = True
    group_class = KeycloakGroup

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = ExtendedCache(self.settings['cache'])
        self.settings.setdefault('logger_name', 'multipass.keycloak')
        self.logger = logging.getLogger(self.settings['logger_name'])

    @property
    def keycloak_settings(self):
        return dict(self.settings['keycloak_args'])

    def get_group(self, name):
        return self.group_class(self, name)

    def search_groups(self, name, exact=False):
        with self._get_api_session() as api_session:
            params = {'search': name,
                      'exact': str(exact).lower(),
                      'populateHierarchy': 'false'}
            url = urljoin(self.keycloak_settings['realm_api_url'] + '/', 'groups')
            response = api_session.get(url, params=params)
            for group in response.json():
                yield self.group_class(self, group['name'])

    def get_identity_groups(self, identifier):
        with self._get_api_session() as api_session:
            # query user details
            params = {'email': identifier,
                      'exact': 'true'}
            url = urljoin(self.keycloak_settings['realm_api_url'] + '/', 'users')
            response = api_session.get(url, params=params)
            if response.status_code == 404:
                return set()
            response.raise_for_status()
            user_data = response.json()[0]
            # query user's groups
            url = urljoin(self.keycloak_settings['realm_api_url'] + '/',
                          f'users/{user_data["id"]}/groups')
            response = api_session.get(url)
            if response.status_code == 404:
                return set()
            response.raise_for_status()
        return {self.group_class(self, group['name']) for group in response.json()}

    @memoize_request
    def _get_api_session(self):
        cache_key = f'flask-multipass-keycloak:{self.name}:api-token'
        api_token = self.cache.get(cache_key)
        api_session = requests.Session()
        if api_token:
            api_session.headers.update({'Authorization': f'Bearer {api_token}'})
            return api_session
        basic = HTTPBasicAuth(self.keycloak_settings['client_name'], self.keycloak_settings['client_secret'])
        data = {'username': self.keycloak_settings['username'],
                'password': self.keycloak_settings['password'],
                'grant_type': 'password'}
        response = api_session.post(self.keycloak_settings['access_token_url'], auth=basic, data=data)
        api_token = response.json()['access_token']
        api_session.headers.update({'Authorization': f'Bearer {api_token}'})
        self.cache.set(cache_key, api_token, response.json()['expires_in'] - 30)
        return api_session

    @memoize_request
    def _get_group_data(self, name):
        params = {'search': name,
                  'exact': 'true',
                  'populateHierarchy': 'false'}
        with self._get_api_session() as api_session:
            group_url = urljoin(self.keycloak_settings['realm_api_url'] + '/', 'groups')
            response = api_session.get(group_url, params=params)
            response.raise_for_status()
            groups = response.json()
        if len(groups) != 1:
            return None
        return groups[0]
