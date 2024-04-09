#!/usr/bin/env bash
# This file is part of Flask-Multipass-Keycloak.
# Copyright (C) 2023 - 2024 CERN & UNCONVENTIONAL

set -e

VERSION=$(grep '^version =' pyproject.toml | cut -d '"' -f 2)
TAG="v${VERSION}"

git tag "${TAG}" -m "Release ${TAG}."
echo "Tag ${TAG} was created"
