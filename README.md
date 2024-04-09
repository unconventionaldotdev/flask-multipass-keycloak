# Flask-Multipass-Keycloak

This package provides the `keycloak` authentication and identity providers for [Flask-Multipass][multipass].

`KeycloakAuthProvider`
This provider is a simple wrapper around [`AuthlibAuthProvider`](https://flask-multipass.readthedocs.io/en/latest/api/#flask_multipass.providers.authlib.AuthlibAuthProvider), since Keycloak works well with the standard `authlib` provider in `flask-multipass`.

`KeycloakIdentityProvider`
This provider gives access to group information and members via Keycloak REST API.

## Install

```
pip install flask-multipass-keycloak
```

## Usage

### Configuration

The configuration follows the standard [Flask-Multipass][multipass] way and the Keycloak specific part placed into the `keycloak_args` section.

```python
MULTIPASS_AUTH_PROVIDERS = {
    'keycloak': {
        'type': 'keycloak',
        'title': 'Keycloak Auth Provider',
        'authlib_args': {...}
    }
}

MULTIPASS_IDENTITY_PROVIDERS = {
    'keycloak': {
        'type': 'keycloak',
        'title': 'Keycloak Identity Provider',
        'identifier_field': 'email',
        'keycloak_args': {
            'client_name': '<client_name>',
            'client_secret': '<client_secret>',
            'username': <username>,
            'password': <password>,
            'access_token_url': <access-token-url>,
            'realm_api_url': <realm-api-url>
        }
    }
}
```

### Performance

The library needs to get an API access token from Keycloak which typically takes 200-300ms. Set the `cache` key of the multipass identity provider configuration to the import path of a Flask-Caching instance or a function returning such an instance, or the instance itself to enable caching of tokens (until they expire) and group data (30 minutes).

## Development

In order to develop `flask-multipass-keycloak`, install the project and its dependencies in a virtualenv. This guide assumes that you have the following tools installed and available in your path:

- [`git`](https://git-scm.com/) (available in most systems)
- [`make`](https://www.gnu.org/software/make/) (available in most systems)
- [`poetry`](https://python-poetry.org/) ([installation guide](https://python-poetry.org/docs/#installation))
- [`pyenv`](https://github.com/pyenv/pyenv) ([installation guide](https://github.com/pyenv/pyenv#installation))

First, clone the repository locally with:

```shell
git clone https://github.com/indico/flask-multipass-keycloak
cd flask-multipass-keycloak
```

Before creating the virtualenv, make sure to be using the same version of Python that the development of the project is targeting. This is the first version specified in the `.python-version` file and you can install it with `pyenv`:

```sh
pyenv install
```

You may now create the virtualenv and install the project with its dependencies in it with `poetry`:

```sh
poetry install
```

### Contributing

This project uses GitHub Actions to run the tests and linter on every pull request. You are still encouraged to run the tests and linter locally before pushing your changes.

Run linter checks with:

```sh
poetry run -- make lint
```

Run tests with:

```sh
poetry run -- make test
```

Run tests against all supported Python versions with:

```sh
tox
```

[multipass]: https://github.com/indico/flask-multipass
