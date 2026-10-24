"""Review fixes for the Azure provider (ticket 17): the OpenAI client's finish
reason errors are labelling failures, the credential ignores the environment,
and nothing in the extra arguments can redirect the bearer token."""

from unittest.mock import MagicMock, patch

import openai
import pytest
from openai.types.chat import ChatCompletion

from cvr.label import LabellerConfig, LabellerMisconfigured, RealLabeller
from cvr.label.azure_openai import azure_kwargs
from cvr.models import Labelling
from cvr.models.feedback import Feedback

ENDPOINT = "https://example-resource.openai.azure.com/"

_EMPTY = Labelling.model_validate(
    {
        "content": {
            "name": None,
            "profile": [],
            "skills": [],
            "education": [],
            "experience": [],
            "certifications": [],
            "additional": [],
        },
        "removals": [],
    }
)


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
        yield cred


def _length_error() -> openai.LengthFinishReasonError:
    completion = ChatCompletion(
        id="x", choices=[], created=0, model="gpt-5.4", object="chat.completion"
    )
    return openai.LengthFinishReasonError(completion=completion)


@pytest.mark.parametrize(
    ("make", "reason"),
    [
        # truncation is what Anthropic's max_tokens becomes: unparseable JSON
        (_length_error, "invalid JSON"),
        # Azure's content filter is a refusal
        (openai.ContentFilterFinishReasonError, "the model refused to answer"),
    ],
)
def test_a_finish_reason_error_is_a_labelling_failure_not_a_500(
    credential, make, reason
):
    first = RealLabeller(_config(), chat_model=MagicMock())
    first._recording._inner = MagicMock(invoke=MagicMock(side_effect=make()))
    result = first([])
    assert result.reason == reason
    assert first.last_run is not None and first.last_run.failure_reason == reason

    retry = RealLabeller(_config(), chat_model=MagicMock())
    retry._retry_recording._inner = MagicMock(invoke=MagicMock(side_effect=make()))
    answer = retry([], feedback=Feedback(), first=_EMPTY)
    assert answer.reason == reason


@pytest.mark.parametrize(
    "extra",
    [
        {"base_url": "https://elsewhere.invalid"},
        {"openai_api_base": "https://elsewhere.invalid"},
        {"azure_endpoint": "https://elsewhere.invalid"},
        {"default_headers": {"x": "y"}},
        {"Default-Headers": {"x": "y"}},
    ],
)
def test_an_argument_that_could_redirect_the_token_is_refused(credential, extra):
    with pytest.raises(LabellerMisconfigured) as raised:
        azure_kwargs(_config(extra=extra), max_retries=2, max_tokens=10)
    assert "redirect" in str(raised.value)
    assert "elsewhere" not in str(raised.value)


def test_the_credential_excludes_the_environment_credential(credential):
    azure_kwargs(_config(), max_retries=2, max_tokens=10)
    credential.assert_called_once_with(exclude_environment_credential=True)
