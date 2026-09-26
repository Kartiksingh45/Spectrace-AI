"""Agent tools - each thin wrapper around an existing retrieval service, scoped to one project/db
session via closures (tools are built fresh per agent invocation, not module-level globals)."""
from typing import Annotated, Any, Callable

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command, interrupt
from sqlalchemy.orm import Session

from app.agent.schemas import GeneratedPlan
from app.core.config import settings
from app.services.embeddings import embed_text
from app.services.retrieval import find_similar_stories as find_similar_stories_service
from app.services.retrieval import get_chunk_context, search_chunks


def _evidence_item(chunk, filename: str, score: float) -> dict[str, Any]:
    content_type = chunk.content_type.value if hasattr(chunk.content_type, "value") else chunk.content_type
    reference = chunk.source_metadata.get("file_path") or filename
    return {
        "chunk_id": str(chunk.id),
        "content_type": content_type,
        "reference": reference,
        "score": score,
    }


def _format_results(rows: list[tuple]) -> str:
    if not rows:
        return "No results found above the relevance threshold."
    lines = []
    for chunk, filename, score in rows:
        lines.append(f"[{chunk.id}] ({filename}, score={score}) {chunk.text[:300]}")
    return "\n\n".join(lines)


def build_tools(
    db: Session,
    project_id,
    plan_generator: Callable[[str, str | None, list[dict], str | None], GeneratedPlan],
) -> list:
    @tool
    def search_requirements(query: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
        """Search uploaded requirement documents for text relevant to the query."""
        rows = search_chunks(
            db, project_id, embed_text(query), "requirement", limit=5, query_text=query, use_reranker=settings.enable_reranker
        )
        evidence = [_evidence_item(chunk, filename, score) for chunk, filename, score in rows]
        return Command(
            update={
                "messages": [
                    ToolMessage(content=_format_results(rows), tool_call_id=tool_call_id, name="search_requirements")
                ],
                "evidence": evidence,
            }
        )

    @tool
    def search_codebase(query: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
        """Search the indexed codebase for functions/classes relevant to the query."""
        rows = search_chunks(
            db, project_id, embed_text(query), "code", limit=5, query_text=query, use_reranker=settings.enable_reranker
        )
        evidence = [_evidence_item(chunk, filename, score) for chunk, filename, score in rows]
        return Command(
            update={
                "messages": [
                    ToolMessage(content=_format_results(rows), tool_call_id=tool_call_id, name="search_codebase")
                ],
                "evidence": evidence,
            }
        )

    @tool
    def get_file_context(chunk_id: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
        """Retrieve the surrounding code/text around a previously found chunk, by its chunk_id."""
        import uuid as _uuid

        try:
            chunks = get_chunk_context(db, _uuid.UUID(chunk_id))
        except ValueError:
            chunks = []
        if not chunks:
            return Command(
                update={
                    "messages": [
                        ToolMessage(content="No such chunk_id.", tool_call_id=tool_call_id, name="get_file_context")
                    ]
                }
            )
        evidence = [
            _evidence_item(c, c.source_metadata.get("filename", c.source_metadata.get("file_path", "")), 1.0)
            for c in chunks
        ]
        text = "\n\n".join(f"[{c.id}] {c.text[:400]}" for c in chunks)
        return Command(
            update={
                "messages": [ToolMessage(content=text, tool_call_id=tool_call_id, name="get_file_context")],
                "evidence": evidence,
            }
        )

    @tool
    def find_similar_stories(query: str) -> str:
        """Find previously approved user stories in this project similar to the query, for context."""
        results = find_similar_stories_service(db, project_id, query)
        if not results:
            return "No similar approved stories found."
        return "\n".join(f"(score={score:.2f}) {summary}" for summary, score in results)

    @tool
    def request_clarification(question: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
        """Pause the run and ask the user a specific clarifying question when required information is missing."""
        answer = interrupt({"type": "clarification", "question": question})
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"User answered: {answer}", tool_call_id=tool_call_id, name="request_clarification"
                    )
                ]
            }
        )

    @tool
    def generate_plan(
        tool_call_id: Annotated[str, InjectedToolCallId], state: Annotated[dict, InjectedState]
    ) -> Command:
        """Produce the structured proposal (user story, acceptance criteria, tasks, test cases, risks)
        once enough evidence has been gathered to responsibly answer the request."""
        # The first HumanMessage is always the original request; any later one is a review
        # correction or reviewer regenerate-feedback note injected by the graph, not the model.
        human_messages = [m for m in state["messages"] if getattr(m, "type", None) == "human"]
        feedback = human_messages[-1].content if len(human_messages) > 1 else None
        plan = plan_generator(state["request_text"], state.get("request_type"), state["evidence"], feedback)
        return Command(
            update={
                "messages": [
                    ToolMessage(content="Plan generated.", tool_call_id=tool_call_id, name="generate_plan")
                ],
                "generated_plan": plan.model_dump(),
            }
        )

    return [
        search_requirements,
        search_codebase,
        get_file_context,
        find_similar_stories,
        request_clarification,
        generate_plan,
    ]
