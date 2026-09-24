"""LabellerConfig reads provider, model, effort, optional temperature and
any other sampling knob from the environment; temperature is absent unless
explicitly set, because Opus 5 rejects an explicit value."""

from cvr.label.config import (
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    LabellerConfig,
)


def test_defaults_are_the_spec_baseline():
    config = LabellerConfig.from_env(env={})
    assert config.provider == DEFAULT_PROVIDER == "anthropic"
    assert config.model == DEFAULT_MODEL == "claude-opus-5-5"
    assert config.effort == DEFAULT_EFFORT == "medium"
    assert config.temperature is None
    assert config.extra == {}


def test_every_field_is_read_from_its_documented_variable():
    config = LabellerConfig.from_env(
        env={
            "CVR_LABEL_PROVIDER": "anthropic",
            "CVR_LABEL_MODEL": "claude-sonnet-5",
            "CVR_LABEL_EFFORT": "high",
            "CVR_LABEL_TEMPERATURE": "0.2",
            "CVR_LABEL_EXTRA": '{"top_p": 0.9}',
        }
    )
    assert config.model == "claude-sonnet-5"
    assert config.effort == "high"
    assert config.temperature == 0.2
    assert config.extra == {"top_p": 0.9}


def test_temperature_absent_when_unset_present_when_set():
    unset = LabellerConfig.from_env(env={})
    assert unset.temperature is None

    empty_string = LabellerConfig.from_env(env={"CVR_LABEL_TEMPERATURE": ""})
    assert empty_string.temperature is None

    set_ = LabellerConfig.from_env(env={"CVR_LABEL_TEMPERATURE": "0.0"})
    assert set_.temperature == 0.0
