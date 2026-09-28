"""LLM-backed BRD (Business Requirements Document) generation - a coder fills in a handful of
plain-language project details (background, objectives, target users, desired features) and the
LLM expands them into a full structured BRD: scope, stakeholders, functional/non-functional
requirements, assumptions, constraints, risks, and success criteria."""
import logging
import time

from app.agent.llm import _get_llm_model
from app.schemas.brd import BrdInput, GeneratedBrd

logger = logging.getLogger(__name__)

BRD_SYSTEM_PROMPT = """You are a business analyst producing a professional Business Requirements \
Document (BRD) from the plain-language project details a developer gives you. Expand their input \
into a complete, well-structured BRD: infer reasonable functional and non-functional requirements, \
risks, assumptions, and success criteria from what they described, but do not invent specific \
facts (numbers, names, dates) they never gave you - note genuine gaps as assumptions instead. \
Keep every item concrete and specific to what was actually described, not generic boilerplate."""

# Gemini occasionally returns a 503 ("This model is currently experiencing high demand") that
# outlasts the google-genai SDK's own few-seconds internal retry - observed in production lasting
# well over ten minutes straight. This outer retry rides out a chunk of that, but this call is
# still synchronous inside the request (unlike the agent run/ingestion, which are backgrounded),
# so the total budget stays well under Render's proxy timeout rather than trying to outlast the
# whole outage - a single retry round that still fails means "try again in a bit", not a hang.
_MAX_RETRIES = 3
_BASE_RETRY_DELAY_SECONDS = 5


def generate_brd(payload: BrdInput) -> GeneratedBrd:
    from google.genai.errors import ServerError
    from langchain_core.messages import HumanMessage, SystemMessage

    model = _get_llm_model().with_structured_output(GeneratedBrd)
    prompt = (
        f"Project name: {payload.project_name}\n"
        f"Background: {payload.background}\n"
        f"Objectives: {payload.objectives}\n"
        f"Target users: {payload.target_users}\n"
        f"Key features requested: {payload.key_features}\n"
    )
    if payload.constraints:
        prompt += f"Known constraints: {payload.constraints}\n"

    messages = [SystemMessage(BRD_SYSTEM_PROMPT), HumanMessage(prompt)]

    for attempt in range(_MAX_RETRIES + 1):
        try:
            return model.invoke(messages)
        except ServerError as exc:
            if exc.code != 503 or attempt == _MAX_RETRIES:
                raise
            delay = _BASE_RETRY_DELAY_SECONDS * (attempt + 1)
            logger.warning(
                "Gemini returned 503 (high demand), retrying in %ss (attempt %s/%s)",
                delay,
                attempt + 1,
                _MAX_RETRIES,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # loop always returns or raises
