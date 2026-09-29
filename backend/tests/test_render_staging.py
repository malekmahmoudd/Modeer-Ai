import hashlib
import json

import pytest

from tools.render_staging import STAGING_USER, prepare_environment


def test_staging_uses_psycopg_and_hashed_invitation():
    env = {
        "FAREEQ_STAGING": "true",
        "DATABASE_URL": "postgres://test:fake@host/fareeq_staging",
        "STAGING_ACCESS_KEY": "x" * 40,
    }
    prepare_environment(env)
    assert env["DATABASE_URL"] == "postgresql+psycopg://test:fake@host/fareeq_staging"
    assert json.loads(env["AUTH_ACCESS_KEYS"]) == {
        STAGING_USER: hashlib.sha256(b"x" * 40).hexdigest()
    }
    assert env["SIGNUP_ENABLED"] == "false"


@pytest.mark.parametrize(
    "change",
    [
        {"FAREEQ_STAGING": "false"},
        {"DATABASE_URL": "postgres://test:fake@host/production"},
        {"DATABASE_URL": "sqlite:///local.db"},
        {"STAGING_ACCESS_KEY": "short"},
    ],
)
def test_staging_refuses_unsafe_bootstrap(change):
    env = {
        "FAREEQ_STAGING": "true",
        "DATABASE_URL": "postgres://test:fake@host/fareeq_staging",
        "STAGING_ACCESS_KEY": "x" * 40,
        **change,
    }
    with pytest.raises(ValueError):
        prepare_environment(env)
