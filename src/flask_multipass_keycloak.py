# This file is part of Flask-Multipass-Keycloak.
# Copyright (C) 2023 - 2024 CERN & UNCONVENTIONAL

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
from werkzeug.exceptions import BadRequest

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
        if not group:
            return None
        with self.provider._get_api_session() as api_session:
            self.provider.logger.info('Requesting group members of "%s"', self.name)
            members = self.provider._fetch_all(api_session, f'groups/{group["id"]}/members')
            identifier_field = self.provider.settings['identifier_field']
            for member in members:
                if identifier_field in member:
                    yield IdentityInfo(self.provider,
                                       member[identifier_field],
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
        self.settings.setdefault('cache', None)
        self.settings.setdefault('logger_name', 'multipass.keycloak')
        self.cache = ExtendedCache(self.settings['cache'])
        self.logger = logging.getLogger(self.settings['logger_name'])

    @property
    def keycloak_settings(self):
        return dict(self.settings['keycloak_args'])

    @staticmethod
    def group_path_as_name(group_path):
        return group_path[1:].replace('/', ' > ')

    @staticmethod
    def group_name_as_path(group_name):
        return f'/{group_name.replace(" > ", "/")}'

    def get_group(self, name):
        return self.group_class(self, name)

    def search_groups(self, name, exact=False):
        with self._get_api_session() as api_session:
            self.logger.info('Requesting matching groups ("%s")', name)
            params = {'search': name,
                      'exact': str(exact).lower(),
                      'populateHierarchy': 'false'}
            groups = self._fetch_all(api_session,'groups', params=params)
            for group in groups:
                yield self.get_group(self.group_path_as_name(group['path']))

    def get_identity_groups(self, identifier):
        with self._get_api_session() as api_session:
            # query user details
            self.logger.info('Requesting data of user "%s"', identifier)
            params = {'email': identifier, 'exact': 'true'}
            users = self._fetch_all(api_session, 'users', params=params)
            if not users:
                return set()
            # query user's groups
            self.logger.info('Requesting groups of "%s"', identifier)
            groups = self._fetch_all(api_session, f'users/{users[0]["id"]}/groups')
        return {self.get_group(group['name']) for group in groups}

    @memoize_request
    def _get_group_data(self, name):
        # API allows searching groups only by name
        _, real_group_name = name.rsplit(' > ', 1)
        group_path = self.group_name_as_path(name)
        params = {'search': real_group_name,
                  'exact': 'true',
                  'populateHierarchy': 'false'}
        with self._get_api_session() as api_session:
            self.logger.info('Requesting data of group "%s"', name)
            groups = self._fetch_all(api_session, 'groups', params=params)
            # Finding the group with the path
            groups = [group for group in groups if group['path'] == group_path]
        if len(groups) != 1:
            return None
        return groups[0]

    def _get_error_message(self, response):
        data = response.json()
        error_message = f'Keycloak API error: {response.status_code} - {data["error"]}'
        if 'error_description' in data:
            error_message += f" - {data['error_description']}"
        return error_message

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
        self.logger.info('Requesting access token')
        response = api_session.post(self.keycloak_settings['access_token_url'], auth=basic, data=data)
        if response.status_code != 200:
            error_message = self._get_error_message(response)
            self.logger.error(f'{error_message} (URL: %s)', response.url)
            raise BadRequest(error_message)
        api_token = response.json()['access_token']
        api_session.headers.update({'Authorization': f'Bearer {api_token}'})
        self.logger.debug('Requested access token will expire in %s s', response.json()['expires_in'])
        self.cache.set(cache_key, api_token, response.json()['expires_in'] - 30)
        return api_session

    def _fetch_all(self, api_session, endpoint, params=None):
        url = urljoin(f'{self.keycloak_settings["realm_api_url"]}/', endpoint)
        response = api_session.get(url, params=params)
        if response.status_code != 200:
            error_message = self._get_error_message(response)
            self.logger.error(f'{error_message} (URL: %s)', response.url)
            raise BadRequest(error_message)
        return response.json()
