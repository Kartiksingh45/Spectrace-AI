import enum


class ContentKind(str, enum.Enum):
    requirement = "requirement"
    code = "code"


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"
