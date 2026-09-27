"""LLM-backed BRD (Business Requirements Document) generation - a coder fills in a handful of
plain-language project details (background, objectives, target users, desired features) and the
LLM expands them into a full structured BRD: scope, stakeholders, functional/non-functional
requirements, assumptions, constraints, risks, and success criteria."""
from app.agent.llm import _get_llm_model
from app.schemas.brd import BrdInput, GeneratedBrd

BRD_SYSTEM_PROMPT = """You are a business analyst producing a professional Business Requirements \
Document (BRD) from the plain-language project details a developer gives you. Expand their input \
into a complete, well-structured BRD: infer reasonable functional and non-functional requirements, \
risks, assumptions, and success criteria from what they described, but do not invent specific \
facts (numbers, names, dates) they never gave you - note genuine gaps as assumptions instead. \
Keep every item concrete and specific to what was actually described, not generic boilerplate."""


def generate_brd(payload: BrdInput) -> GeneratedBrd:
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

    return model.invoke([SystemMessage(BRD_SYSTEM_PROMPT), HumanMessage(prompt)])
