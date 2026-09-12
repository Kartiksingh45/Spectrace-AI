import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class EvidenceItem(TypedDict):
    chunk_id: str
    content_type: str  # "requirement" | "code"
    reference: str  # filename for requirement chunks, file_path for code chunks
    score: float


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    request_text: str
    request_type: str | None
    evidence: Annotated[list[EvidenceItem], operator.add]
    generated_plan: dict[str, Any] | None
    generated_plan_valid: bool
    review_retries: int
    step_count: int
    final_decision: dict[str, Any] | None
