"""F2 只读接口和教学数据使用的对象结构。"""

from pydantic import BaseModel, Field


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


class Material(BaseModel):
    material_id: str
    application_id: str
    material_type: str
    file_name: str
    version_no: int = Field(ge=1)
    check_status: str
    preview_url: str | None
    submitted_at: str


class KnowledgeItem(BaseModel):
    knowledge_id: str
    version: str
    requirement: str


class EvidenceRef(BaseModel):
    material_id: str
    file_name: str
    page: int = Field(ge=1)
    quote: str


class ReportItem(BaseModel):
    """一条预审线索；证据和知识依据供人工核验，不是审批结论。"""

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


class Report(BaseModel):
    """一次预审运行的结果；失败时保留原因，不能按空报告处理。"""

    report_id: str
    application_id: str
    generated_at: str
    analysis_status: str
    knowledge_version: str
    error_message: str | None
    items: list[ReportItem]


class SeedData(BaseModel):
    enterprises: list[Enterprise]
    applications: list[Application]
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
    materials: list[Material]
    reports: list[Report]
