"""F2 只读接口和教学数据使用的对象结构。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Enterprise(BaseModel):
    enterprise_id: str
    enterprise_name: str
    industry: str
    registered_region: str
    created_at: str


class Application(BaseModel):
    """一笔申请只对应一种教学产品需求，金额单位为元。"""

    application_id: str
    enterprise_id: str
    product_type: str
    requested_amount: int = Field(ge=0)
    status: str
    account_manager_id: str
    account_manager_name: str
    submitted_at: str
    purpose: str | None = None


class ApplicationSubmission(BaseModel):
    """企业端提交的虚构教学申请；不接受客户端指定状态。"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    enterprise_name: str = Field(min_length=1, max_length=150)
    industry: str = Field(min_length=1, max_length=100)
    registered_region: str = Field(min_length=1, max_length=100)
    product_type: Literal['经营周转贷（教学产品）', '设备更新贷（教学产品）']
    requested_amount: int = Field(gt=0, le=100000000)
    purpose: str = Field(min_length=1, max_length=1000)


class StatusEvent(BaseModel):
    """一条虚构进度事件，不代表正式审计记录。"""

    event_id: str
    application_id: str
    event_label: str
    occurred_at: str


class Material(BaseModel):
    material_id: str
    application_id: str
    material_type: str
    file_name: str
    version_no: int = Field(ge=1)
    check_status: str
    preview_url: str | None
    submitted_at: str
    sample_location: str | None = None
    sample_excerpt: str | None = None


class KnowledgeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_id: str
    version: str
    requirement: str


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str
    file_name: str
    page: int = Field(ge=1)
    quote: str


class ReportItem(BaseModel):
    """一条预审线索；证据和知识依据供人工核验，不是审批结论。"""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    item_type: str
    field_name: str
    match_status: str
    application_value: str | None
    material_value: str | None
    evidence: list[EvidenceRef]
    knowledge_ref: KnowledgeItem | None
    reason: str
    confidence: str
    suggested_human_action: str


class ReportAspect(BaseModel):
    """报告摘要维度；引用已有材料、关注项和教学知识，不给审批结论。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["needs_review", "insufficient_evidence", "not_evaluated"]
    summary: str = Field(min_length=1)
    material_ids: list[str] = Field(default_factory=list)
    item_ids: list[str] = Field(default_factory=list)
    knowledge_refs: list[KnowledgeItem] = Field(default_factory=list)


class Report(BaseModel):
    """一次预审运行的结果；失败时保留原因，不能按空报告处理。"""

    model_config = ConfigDict(extra="forbid")

    report_id: str
    application_id: str
    generated_at: str
    analysis_status: str
    knowledge_version: str
    error_message: str | None
    items: list[ReportItem]
    material_completeness: ReportAspect
    risk_prompts: list[ReportAspect]
    policy_match: ReportAspect
    precheck_advice: ReportAspect


class ItemReview(BaseModel):
    item_id: str
    decision: Literal["confirmed", "corrected"]
    correction_note: str | None = Field(default=None, max_length=1000)


class ReviewSubmission(BaseModel):
    review_result: Literal["complete", "request_supplement"]
    review_note: str = Field(min_length=1, max_length=2000)
    item_reviews: list[ItemReview]


class ReviewRecord(ReviewSubmission):
    review_id: str
    application_id: str
    report_id: str | None
    reviewer_id: str
    reviewed_at: str


class SeedData(BaseModel):
    enterprises: list[Enterprise]
    applications: list[Application]
    status_events: list[StatusEvent]
    materials: list[Material]
    knowledge_items: list[KnowledgeItem]
    reports: list[Report]


class ApplicationSummary(Application):
    enterprise_name: str
    report_status: str | None


class ApplicationDetail(BaseModel):
    """同一申请下的企业、材料和历次报告。"""

    application: Application
    enterprise: Enterprise
    status_history: list[StatusEvent]
    materials: list[Material]
    reports: list[Report]
    reviews: list[ReviewRecord] = Field(default_factory=list)
