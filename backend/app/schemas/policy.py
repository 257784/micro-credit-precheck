"""政策问答协议；校验引用，不包含任何审批动作。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Product = Literal["working_capital", "equipment"]


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    product: Product | None = None
    rerank: bool = False

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(pattern=r"^S[1-6]$")
    quote: str = Field(min_length=8, max_length=1200)

    @field_validator("quote")
    @classmethod
    def meaningful_quote(cls, value: str) -> str:
        if len("".join(value.split())) < 8:
            raise ValueError("引用至少包含8个非空白字符")
        return value


class Statement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)
    evidence: list[Evidence] = Field(min_length=1, max_length=6)


class AnswerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["answered", "insufficient_evidence", "needs_clarification"]
    statements: list[Statement] = Field(max_length=12)
    missing_information: list[str] = Field(max_length=8)


class PolicySource(BaseModel):
    source_id: str
    chunk_id: str
    document_id: str
    version: str
    clause: str
    title: str
    source_path: str
    source_line: int
    text: str
    cosine_distance: float | None


class QuestionResponse(BaseModel):
    status: Literal[
        "answered", "insufficient_evidence", "needs_clarification", "out_of_scope",
        "configuration_error", "retrieval_error", "generation_error",
    ]
    answer: str
    statements: list[Statement] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    sources: list[PolicySource] = Field(default_factory=list)
    cited_source_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model: str | None = None
    prompt_version: str = "policy-qa-v1"
    retrieval_k: int = 8
    context_k: int = 6
    elapsed_seconds: float = 0
    error_code: str | None = None
    notice: str = "仅依据虚构教学政策解释，不构成授信、审批或放款决定。"
