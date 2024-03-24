# Flask-Multipass-Keycloak

This package provides the `keycloak` auth and identity providers for [Flask-Multipass][multipass].

The package delivers 2 providers:
* `KeycloakAuthProvider`

  Currently it is nothing else than the `AuthlibAuthProvider`, since Keycloak works well with the standard `authlib` multipass provider.
* `KeycloakIdentityProvider`

  In its current state it provides access to group information and members utilising Keycloak REST API.

## Install

```
pip install git+https://github.com/indico/flask-multipass-keycloak.git
```

## Configuration

The configuration follows the standard [Flask-Multipass][multipass] way and the Keycloak specific part placed into the `keycloak_args` section.

```
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

## Performance

The library needs to get an API access token from Keycloak which typically takes 200-300ms. Set the `cache` key of the multipass identity
provider configuration to the import path of a Flask-Caching instance or a function returning such
an instance, or the instance itself to enable caching of tokens (until they expire) and group
data (30 minutes).

[multipass]: https://github.com/indico/flask-multipass
