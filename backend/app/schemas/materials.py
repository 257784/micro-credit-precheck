"""完整性Workflow的独立教学输入，不改变F2材料对象的字段语义。"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: bool | None = Field(strict=True)
    source: Literal["manual_demo", "fixture", "application_field"]
    location: str = Field(min_length=1, max_length=300)

    @field_validator("location")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("事实来源位置不能为空")
        return value.strip()


class Conditions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uses_order_contract: Fact | None = None
    is_used_equipment: Fact | None = None


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_code: str
    evidence_location: str = Field(min_length=1, max_length=300)
    source: Literal["manual_demo", "fixture"]
    checked_fields: list[str] = Field(default_factory=list, max_length=30)
    extracted_fields: dict[str, Any] = Field(default_factory=dict)


class WorkflowMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_id: str = Field(min_length=1, max_length=100)
    application_id: str
    material_type: str = Field(min_length=1, max_length=100)
    file_name: str = Field(min_length=1, max_length=300)
    version_no: int = Field(ge=1, strict=True)
    canonical_code: str | None = None
    mapping_source: str | None = Field(default=None, max_length=300)
    parse_status: Literal["parsed_mock", "parsed", "failed", "not_available"] = "not_available"
    checked_fields: list[str] = Field(default_factory=list, max_length=30)
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    evidence_location: str | None = Field(default=None, max_length=300)
    sample_excerpt: str | None = Field(default=None, max_length=8000)
    sections: list[Section] = Field(default_factory=list, max_length=12)

    @field_validator("material_id", "application_id", "material_type", "file_name")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("材料标识、类型和文件名不能为空")
        return value.strip()

    @model_validator(mode="after")
    def explicit_mapping(self):
        if self.canonical_code and not (self.mapping_source or "").strip():
            raise ValueError("显式归类必须记录人工/fixture来源")
        if self.parse_status not in ("parsed_mock", "parsed") and (self.checked_fields or self.extracted_fields):
            raise ValueError("无Mock解析结果时不能提供已检查字段")
        return self


class WorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application_id: str = Field(min_length=1, max_length=100)
    product: str | None
    input_mode: Literal["legacy_metadata", "mock_parsed", "uploaded_documents"]
    conditions: Conditions = Field(default_factory=Conditions)
    materials: list[WorkflowMaterial] = Field(max_length=100)


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    use_model: bool = Field(default=False, strict=True)
    conditions: Conditions = Field(default_factory=Conditions)

    @model_validator(mode="after")
    def manual_facts_only(self):
        if any(fact and fact.source != "manual_demo" for fact in
               (self.conditions.uses_order_contract, self.conditions.is_used_equipment)):
            raise ValueError("API请求中的条件事实只能标注为人工演示声明")
        return self
