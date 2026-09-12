"""Real Groq-backed LLM calls used by the agent graph.

Kept as small, independently injectable functions (rather than methods on the graph) so tests can
substitute deterministic stubs without needing to fake ChatGroq's tool-calling wire format.
"""
from typing import Literal

from pydantic import BaseModel

from app.agent.schemas import GeneratedPlan
from app.agent.state import EvidenceItem
from app.core.config import settings


class ClassifyResult(BaseModel):
    request_type: Literal["feature", "bug", "refactor", "security", "performance", "documentation"]


CLASSIFY_PROMPT = (
    "Classify the following software change request into exactly one category: "
    "feature, bug, refactor, security, performance, or documentation."
)

PLAN_SYSTEM_PROMPT = """You are producing a structured impact-analysis plan for a software change \
request. You may cite ONLY evidence chunk_ids and file paths that appear in the evidence list below \
- never invent one. If the evidence is insufficient to responsibly complete a field, say so in \
`assumptions` or `risks` rather than fabricating specifics. Set `confidence` honestly based on how \
well the evidence actually supports the plan."""


def _get_groq_model():
    from langchain_groq import ChatGroq

    return ChatGroq(model=settings.groq_model_name, api_key=settings.groq_api_key, temperature=0)


def classify_request(request_text: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    model = _get_groq_model().with_structured_output(ClassifyResult)
    result = model.invoke([SystemMessage(CLASSIFY_PROMPT), HumanMessage(request_text)])
    return result.request_type


def _format_evidence(evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return "(no evidence gathered yet)"
    lines = []
    for item in evidence:
        lines.append(f"- chunk_id={item['chunk_id']} type={item['content_type']} ref={item['reference']}")
    return "\n".join(lines)


def generate_plan_with_llm(
    request_text: str, request_type: str | None, evidence: list[EvidenceItem], feedback: str | None
) -> GeneratedPlan:
    from langchain_core.messages import HumanMessage, SystemMessage

    model = _get_groq_model().with_structured_output(GeneratedPlan)
    prompt = (
        f"Request: {request_text}\n"
        f"Request type: {request_type or 'unknown'}\n\n"
        f"Evidence gathered this run:\n{_format_evidence(evidence)}\n"
    )
    if feedback:
        prompt += f"\nCorrection needed from a previous attempt: {feedback}\n"

    return model.invoke([SystemMessage(PLAN_SYSTEM_PROMPT), HumanMessage(prompt)])
