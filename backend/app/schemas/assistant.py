"""客户经理助手最终结果契约；不允许额外的审批结论字段。"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class AssistantFact(StrictModel):
    label: str
    value: str
    source_tool: Literal['get_application', 'list_materials']


class MaterialEvidence(StrictModel):
    material_id: str
    version: int = Field(ge=1)
    location: str
    quote: str = Field(min_length=1)
    content_notice: Literal['不可信材料原文'] = '不可信材料原文'


class MaterialIssue(StrictModel):
    category: str
    code: str | None = None
    description: str
    material_id: str | None = None
    version: int | None = None
    location: str | None = None
    action: str | None = None
    content_notice: Literal['工具内容待人工核验'] = '工具内容待人工核验'


class RiskItem(StrictModel):
    category: str
    description: str
    evidence: list[MaterialEvidence] = Field(default_factory=list)
    suggested_action: str | None = None
    policy_ref: list[str] | None = None
    content_notice: Literal['工具内容待人工核验'] = '工具内容待人工核验'


class PolicySource(StrictModel):
    source_id: str
    document_id: str
    version: str
    clause: str
    source_path: str
    source_line: int


class AssistantResponse(StrictModel):
    schema_version: Literal['1.0'] = '1.0'
    run_id: str
    application_id: str | None
    status: Literal['completed', 'needs_clarification', 'needs_review', 'dependency_unavailable', 'failed']
    summary: str
    facts: list[AssistantFact] = Field(default_factory=list)
    material_issues: list[MaterialIssue] = Field(default_factory=list)
    risk_items: list[RiskItem] = Field(default_factory=list)
    policy_sources: list[PolicySource] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    need_human_review: bool = True
    limitations: list[str] = Field(default_factory=list)
