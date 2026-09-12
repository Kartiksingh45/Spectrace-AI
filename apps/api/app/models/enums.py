import enum


class ContentKind(str, enum.Enum):
    requirement = "requirement"
    code = "code"


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class RequestType(str, enum.Enum):
    feature = "feature"
    bug = "bug"
    refactor = "refactor"
    security = "security"
    performance = "performance"
    documentation = "documentation"


class ChangeRequestStatus(str, enum.Enum):
    pending = "pending"
    analysing = "analysing"
    awaiting_clarification = "awaiting_clarification"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"
    failed = "failed"


class AgentRunStatus(str, enum.Enum):
    running = "running"
    awaiting_clarification = "awaiting_clarification"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"


class AgentStepStatus(str, enum.Enum):
    ok = "ok"
    error = "error"


class ApprovalDecision(str, enum.Enum):
    approved = "approved"
    edit_approved = "edit_approved"
    rejected = "rejected"
    regenerate_requested = "regenerate_requested"


class EvaluationCategory(str, enum.Enum):
    """The four BRD 14.1 dataset buckets (6/4/3/2 minimum cases respectively)."""

    clear = "clear"
    cross_source = "cross_source"
    ambiguous = "ambiguous"
    unsupported = "unsupported"


class EvaluationBehavior(str, enum.Enum):
    direct_answer = "direct_answer"
    clarification = "clarification"
    insufficient_evidence = "insufficient_evidence"
    failed = "failed"
