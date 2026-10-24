"""The Azure OpenAI provider (ticket 17), over fakes only: the credential and
the chat-model constructor are patched, so nothing reaches Azure. What is
pinned: an Azure configuration yields the expected chat-model arguments and a
token provider, never a key; a configuration carrying a key is refused as
misconfigured; the Azure client's errors are classified like Anthropic's; and
the structured output is strict."""

from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest
from azure.core import exceptions as azure_exceptions
from langchain_openai import AzureChatOpenAI

from cvr.label import LabellerConfig, LabellerMisconfigured, ProviderUnavailable
from cvr.label.azure_openai import AZURE_EFFORTS, azure_error, azure_kwargs
from cvr.label.config import (
    DEFAULT_AZURE_API_VERSION,
    DEFAULT_AZURE_SCOPE,
)
from cvr.label.config import (
    LabellerConfig as Config,
)
from cvr.label.labeller import (
    MAX_OUTPUT_TOKENS,
    PROVIDER_RETRIES,
    RealLabeller,
    _structured_model,
    build_chat_model,
)
from cvr.models import Additions, Labelling

ENDPOINT = "https://example-resource.openai.azure.com/"


def _config(**overrides) -> LabellerConfig:
    fields = {
        "provider": "azure_openai",
        "model": "gpt-5.4",
        "azure_endpoint": ENDPOINT,
    } | overrides
    return LabellerConfig(**fields)


@pytest.fixture
def credential():
    with (
        patch("cvr.label.azure_openai.DefaultAzureCredential") as cred,
        patch("cvr.label.azure_openai.get_bearer_token_provider") as provider,
    ):
        provider.return_value = lambda: "token"
        yield cred, provider


def test_azure_arguments_carry_a_token_provider_and_no_key(credential):
    cred, provider = credential
    kwargs = azure_kwargs(
        _config(), max_retries=PROVIDER_RETRIES, max_tokens=MAX_OUTPUT_TOKENS
    )
    provider.assert_called_once_with(cred.return_value, DEFAULT_AZURE_SCOPE)
    assert DEFAULT_AZURE_SCOPE == "https://ai.azure.com/.default"
    assert kwargs == {
        "azure_endpoint": ENDPOINT,
        "azure_deployment": "gpt-5.4",
        "api_version": DEFAULT_AZURE_API_VERSION,
        "azure_ad_token_provider": provider.return_value,
        "api_key": None,
        "azure_ad_token": None,
        "reasoning_effort": "medium",
        "max_retries": 2,
        "max_completion_tokens": 128_000,
    }


def test_deployment_version_and_scope_come_from_the_config(credential):
    _, provider = credential
    kwargs = azure_kwargs(
        _config(
            azure_deployment="cv-labeller",
            azure_api_version="2099-01-01-preview",
            azure_scope="https://cognitiveservices.azure.com/.default",
        ),
        max_retries=2,
        max_tokens=10,
    )
    assert kwargs["azure_deployment"] == "cv-labeller"
    assert kwargs["api_version"] == "2099-01-01-preview"
    assert provider.call_args.args[1] == "https://cognitiveservices.azure.com/.default"


def test_temperature_is_sent_only_when_set_and_extra_passes_through(credential):
    plain = azure_kwargs(_config(), max_retries=2, max_tokens=10)
    assert "temperature" not in plain
    tuned = azure_kwargs(
        _config(temperature=0.2, extra={"top_p": 0.9}), max_retries=2, max_tokens=10
    )
    assert tuned["temperature"] == 0.2
    assert tuned["top_p"] == 0.9


@pytest.mark.parametrize(
    "extra",
    [
        {"api_key": "secret-value"},
        {"openai_api_key": "secret-value"},
        {"azure_ad_token": "secret-value"},
        {"azure_ad_token_provider": "secret-value"},
        {"azure_ad_async_token_provider": "secret-value"},
        {"API-KEY": "secret-value"},
    ],
)
def test_a_config_carrying_a_key_is_refused(credential, extra):
    with pytest.raises(LabellerMisconfigured) as raised:
        azure_kwargs(_config(extra=extra), max_retries=2, max_tokens=10)
    assert "keyless" in str(raised.value)
    assert "secret-value" not in str(raised.value)


def test_a_key_in_the_environment_is_refused_by_build_chat_model(credential):
    env = {"CVR_LABEL_PROVIDER": "azure_openai", "CVR_LABEL_EXTRA": '{"api_key": "k"}'}
    config = LabellerConfig.from_env(env | {"CVR_LABEL_AZURE_ENDPOINT": ENDPOINT})
    with pytest.raises(LabellerMisconfigured):
        build_chat_model(config)


def test_the_endpoint_is_required(credential):
    with pytest.raises(LabellerMisconfigured, match="CVR_LABEL_AZURE_ENDPOINT"):
        azure_kwargs(_config(azure_endpoint=None), max_retries=2, max_tokens=10)


@pytest.mark.parametrize("effort", AZURE_EFFORTS)
def test_the_efforts_gpt_5_4_accepts_pass_through(credential, effort):
    kwargs = azure_kwargs(_config(effort=effort), max_retries=2, max_tokens=10)
    assert kwargs["reasoning_effort"] == effort


def test_max_effort_is_refused_for_azure(credential):
    with pytest.raises(LabellerMisconfigured, match="max"):
        azure_kwargs(_config(effort="max"), max_retries=2, max_tokens=10)


def test_build_chat_model_passes_the_azure_arguments_to_init_chat_model(credential):
    with patch("cvr.label.labeller.init_chat_model") as init:
        build_chat_model(_config())
    init.assert_called_once()
    assert init.call_args.kwargs["model"] == "gpt-5.4"
    assert init.call_args.kwargs["model_provider"] == "azure_openai"
    assert init.call_args.kwargs["azure_endpoint"] == ENDPOINT
    assert init.call_args.kwargs["api_key"] is None
    assert callable(init.call_args.kwargs["azure_ad_token_provider"])


def test_a_real_azure_chat_model_never_picks_up_a_key_from_the_environment(
    credential, monkeypatch
):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("AZURE_OPENAI_AD_TOKEN", "env-token")
    model = build_chat_model(_config())
    assert isinstance(model, AzureChatOpenAI)
    assert model.openai_api_key is None
    assert model.azure_ad_token is None
    assert model.azure_ad_token_provider is not None
    assert model.deployment_name == "gpt-5.4"
    assert model.reasoning_effort == "medium"
    assert model.max_tokens == 128_000
    assert model.max_retries == PROVIDER_RETRIES
    params = model._default_params
    assert params["max_completion_tokens"] == 128_000
    assert "max_tokens" not in params
    assert "temperature" not in params or params["temperature"] is None


def test_the_azure_structured_output_is_strict_json_schema(credential):
    chat_model = MagicMock()
    _structured_model(chat_model, strict=True)
    chat_model.with_structured_output.assert_called_once_with(
        Labelling, include_raw=True, method="json_schema", strict=True
    )
    anthropic_model = MagicMock()
    _structured_model(anthropic_model)
    anthropic_model.with_structured_output.assert_called_once_with(
        Labelling, include_raw=True, method="json_schema"
    )


def test_real_labeller_binds_both_schemas_strictly_on_azure(credential):
    chat_model = MagicMock()
    RealLabeller(_config(), chat_model=chat_model)
    calls = chat_model.with_structured_output.call_args_list
    assert [call.args[0] for call in calls] == [Labelling, Additions]
    assert all(call.kwargs["strict"] is True for call in calls)


def test_real_labeller_binds_anthropic_without_strict():
    chat_model = MagicMock()
    RealLabeller(LabellerConfig(), chat_model=chat_model)
    assert all(
        "strict" not in call.kwargs
        for call in chat_model.with_structured_output.call_args_list
    )


def test_the_azure_settings_are_read_from_the_environment():
    config = Config.from_env(
        {
            "CVR_LABEL_PROVIDER": "azure_openai",
            "CVR_LABEL_MODEL": "gpt-5.4",
            "CVR_LABEL_AZURE_ENDPOINT": ENDPOINT,
            "CVR_LABEL_AZURE_DEPLOYMENT": "dep",
            "CVR_LABEL_AZURE_API_VERSION": "v",
            "CVR_LABEL_AZURE_SCOPE": "s",
        }
    )
    assert (config.azure_endpoint, config.azure_deployment) == (ENDPOINT, "dep")
    assert (config.azure_api_version, config.azure_scope) == ("v", "s")


def test_as_dict_is_unchanged_for_anthropic_and_hides_the_endpoint_for_azure():
    assert set(Config().as_dict()) == {
        "provider",
        "model",
        "effort",
        "temperature",
        "extra",
    }
    azure = _config(azure_deployment="dep").as_dict()
    assert azure["azure_deployment"] == "dep"
    assert ENDPOINT not in str(azure)


_REQUEST = httpx.Request("POST", "https://example-resource.openai.azure.com/x")


def _status(cls: type[openai.APIStatusError], status: int) -> Exception:
    return cls(
        "echoed model text",
        response=httpx.Response(status, request=_REQUEST),
        body=None,
    )


@pytest.mark.parametrize(
    "exc",
    [
        _status(openai.AuthenticationError, 401),
        _status(openai.PermissionDeniedError, 403),
        _status(openai.NotFoundError, 404),
        _status(openai.BadRequestError, 400),
        azure_exceptions.ClientAuthenticationError("no credential"),
    ],
)
def test_a_rejected_request_or_credential_is_misconfigured(exc):
    error = azure_error(exc, PROVIDER_RETRIES)
    assert isinstance(error, LabellerMisconfigured)
    assert "echoed model text" not in str(error)


@pytest.mark.parametrize(
    "exc",
    [
        _status(openai.RateLimitError, 429),
        _status(openai.InternalServerError, 500),
        openai.APIConnectionError(request=_REQUEST),
        openai.APITimeoutError(request=_REQUEST),
        azure_exceptions.ServiceRequestError("no route"),
    ],
)
def test_a_transient_failure_is_provider_unavailable(exc):
    error = azure_error(exc, PROVIDER_RETRIES)
    assert isinstance(error, ProviderUnavailable)
    assert "echoed model text" not in str(error)


def test_anything_else_is_not_a_provider_error():
    assert azure_error(ValueError("x"), PROVIDER_RETRIES) is None


def test_the_labeller_classifies_an_azure_error_raised_by_the_call(credential):
    exc = _status(openai.RateLimitError, 429)
    chat_model = MagicMock()
    labeller = RealLabeller(_config(), chat_model=chat_model)
    labeller._recording._inner = MagicMock(invoke=MagicMock(side_effect=exc))
    with pytest.raises(ProviderUnavailable) as raised:
        labeller([])
    assert raised.value.__cause__ is None and raised.value.__context__ is None


def test_an_openai_refusal_is_a_labelling_failure(credential):
    refusal = MagicMock(
        usage_metadata={"input_tokens": 3, "output_tokens": 1},
        response_metadata={"finish_reason": "stop"},
        additional_kwargs={"refusal": "I cannot help with that"},
    )
    chat_model = MagicMock()
    labeller = RealLabeller(_config(), chat_model=chat_model)
    labeller._recording._inner = MagicMock(
        invoke=MagicMock(
            return_value={"raw": refusal, "parsed": None, "parsing_error": None}
        )
    )
    result = labeller([])
    assert result.reason == "the model refused to answer"
    assert "cannot help" not in result.reason
    assert labeller.last_run is not None
    # gpt-5.4 is priced, so the refused call's tokens still cost something.
    assert labeller.last_run.cost_usd == pytest.approx((3 * 2.75 + 1 * 16.5) / 1e6)
