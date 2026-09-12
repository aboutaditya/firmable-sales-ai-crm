#!/usr/bin/env sh
set -eu
: "${DATABASE_URL:?DATABASE_URL must be set}"
alembic upgrade head
