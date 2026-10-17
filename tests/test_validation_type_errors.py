"""Invalid user input remains a Pydantic/configuration error, not TypeError."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import loader
from app.config.loader import ConfigValidationError, load_and_validate_config
from app.config.validation import ImpulseConfig
from impulse_messenger_api import BaseUser


@pytest.mark.parametrize("value", [None, [], "none", 123, True])
def test_non_mapping_messenger_is_a_validation_error(value):
    with pytest.raises(ValidationError) as caught:
        ImpulseConfig(messenger=value)
    error = caught.value.errors()[0]
    assert error["loc"] == ("messenger",)
    assert error["type"] == "value_error"
    assert error["msg"] == "Value error, Messenger configuration must be a mapping"


@pytest.mark.parametrize("value", [True, False])
def test_boolean_user_id_is_a_validation_error(value):
    with pytest.raises(ValidationError) as caught:
        BaseUser(id=value)
    error = caught.value.errors()[0]
    assert error["loc"] == ("id",)
    assert error["type"] == "value_error"
    assert error["msg"] == "Value error, ID must be a string or integer, not a boolean"


@pytest.mark.parametrize("value", ["U1", 123])
def test_valid_user_ids_keep_their_type_and_value(value):
    user = BaseUser(id=value)
    assert user.id == value
    assert type(user.id) is type(value)


def test_messenger_type_error_is_reported_by_config_loader(tmp_path: Path, monkeypatch):
    # The global suite fixture mocks configuration loading. Keep this test on
    # the real loader function imported during collection and its real model.
    monkeypatch.setattr(loader, "validate_config", ImpulseConfig.model_validate)
    config = tmp_path / "impulse.yml"
    config.write_text("messenger: false\n", encoding="utf-8")
    with pytest.raises(ConfigValidationError) as caught:
        load_and_validate_config(str(config))
    assert "Messenger configuration must be a mapping" in str(caught.value)
    assert caught.value.validation_errors[0]["loc"] == ("messenger",)
    assert caught.value.validation_errors[0]["type"] == "value_error"
