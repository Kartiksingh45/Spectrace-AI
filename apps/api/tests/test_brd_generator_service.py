from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import ClientError, ServerError

from app.schemas.brd import BrdInput, GeneratedBrd
from app.services.brd_generator import generate_brd


def _payload() -> BrdInput:
    return BrdInput(
        project_name="Test",
        background="background",
        objectives="objectives",
        target_users="users",
        key_features="features",
    )


def _fake_result() -> GeneratedBrd:
    return GeneratedBrd(
        executive_summary="summary",
        business_objectives=["a"],
        in_scope=["a"],
        out_of_scope=["a"],
        stakeholders=["a"],
        functional_requirements=[],
        non_functional_requirements=[],
        success_criteria=["a"],
    )


def _service_unavailable() -> ServerError:
    return ServerError(503, {"error": {"message": "This model is currently experiencing high demand."}}, None)


@patch("app.services.brd_generator._get_llm_model")
@patch("app.services.brd_generator.time.sleep")
def test_generate_brd_retries_on_503_then_succeeds(mock_sleep, mock_get_model):
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = [_service_unavailable(), _service_unavailable(), _fake_result()]
    mock_get_model.return_value.with_structured_output.return_value = mock_structured

    result = generate_brd(_payload())

    assert result.executive_summary == "summary"
    assert mock_structured.invoke.call_count == 3
    assert mock_sleep.call_count == 2


@patch("app.services.brd_generator._get_llm_model")
@patch("app.services.brd_generator.time.sleep")
def test_generate_brd_gives_up_after_max_retries(mock_sleep, mock_get_model):
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = _service_unavailable()
    mock_get_model.return_value.with_structured_output.return_value = mock_structured

    with pytest.raises(ServerError):
        generate_brd(_payload())

    assert mock_structured.invoke.call_count == 4  # initial attempt + 3 retries


@patch("app.services.brd_generator._get_llm_model")
@patch("app.services.brd_generator.time.sleep")
def test_generate_brd_does_not_retry_other_errors(mock_sleep, mock_get_model):
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = ClientError(429, {"error": {"message": "quota"}}, None)
    mock_get_model.return_value.with_structured_output.return_value = mock_structured

    with pytest.raises(ClientError):
        generate_brd(_payload())

    assert mock_structured.invoke.call_count == 1
    mock_sleep.assert_not_called()
