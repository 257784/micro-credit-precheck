"""加载虚构教学数据，并验证跨对象引用与只读查询关系。"""

from datetime import datetime
from pathlib import Path

from app.schemas.business import (
    ApplicationDetail,
    ApplicationSummary,
    Enterprise,
    Report,
    SeedData,
)

from app.core.config import PROJECT_ROOT
SEED_PATH = PROJECT_ROOT / "mock_data" / "seed.json"


def load_seed(path: Path = SEED_PATH) -> SeedData:
    """读取并校验样例；ID 重复或引用失效时拒绝启动服务。"""

    data = SeedData.model_validate_json(path.read_text(encoding="utf-8"))
    enterprises = {item.enterprise_id: item for item in data.enterprises}
    applications = {item.application_id: item for item in data.applications}
    status_events = {item.event_id: item for item in data.status_events}
    materials = {item.material_id: item for item in data.materials}
    knowledge = {(item.knowledge_id, item.version): item for item in data.knowledge_items}

    for label, items, ids in (
        ("enterprise", data.enterprises, enterprises),
        ("application", data.applications, applications),
        ("status event", data.status_events, status_events),
        ("material", data.materials, materials),
    ):
        if len(items) != len(ids):
            raise ValueError(f"Duplicate {label} ID in {path}")
    if len(data.reports) != len({item.report_id for item in data.reports}):
        raise ValueError(f"Duplicate report ID in {path}")
    if len(data.knowledge_items) != len(knowledge):
        raise ValueError(f"Duplicate knowledge ID/version in {path}")

    for application in data.applications:
        if application.enterprise_id not in enterprises:
            raise ValueError(f"Unknown enterprise for {application.application_id}")
    for event in data.status_events:
        if event.application_id not in applications:
            raise ValueError(f"Unknown application for {event.event_id}")
        event_time = datetime.fromisoformat(event.occurred_at)
        if event_time.utcoffset() is None:
            raise ValueError(f"Missing timezone for {event.event_id}")
    material_versions = set()
    for material in data.materials:
        if material.application_id not in applications:
            raise ValueError(f"Unknown application for {material.material_id}")
        version_key = (material.application_id, material.material_type, material.version_no)
        if version_key in material_versions:
            raise ValueError(f"Duplicate material version for {material.material_id}")
        material_versions.add(version_key)
        if bool(material.sample_location) != bool(material.sample_excerpt):
            raise ValueError(f"Incomplete sample excerpt for {material.material_id}")
    for report in data.reports:
        if report.application_id not in applications:
            raise ValueError(f"Unknown application for {report.report_id}")
        item_ids = {item.item_id for item in report.items}
        if len(item_ids) != len(report.items):
            raise ValueError(f"Duplicate report item ID in {report.report_id}")
        if report.analysis_status == "failed" and report.risk_prompts:
            raise ValueError(f"Failed report cannot contain risk prompts in {report.report_id}")
        aspects = [
            ("material_completeness", report.material_completeness),
            ("policy_match", report.policy_match),
            ("precheck_advice", report.precheck_advice),
        ]
        aspects.extend(
            (f"risk_prompts[{index}]", aspect)
            for index, aspect in enumerate(report.risk_prompts)
        )
        for name, aspect in aspects:
            for material_id in aspect.material_ids:
                material = materials.get(material_id)
                if material is None or material.application_id != report.application_id:
                    raise ValueError(f"Invalid material reference in {report.report_id}.{name}")
            if any(item_id not in item_ids for item_id in aspect.item_ids):
                raise ValueError(f"Invalid item reference in {report.report_id}.{name}")
            for reference in aspect.knowledge_refs:
                key = (reference.knowledge_id, reference.version)
                if key not in knowledge or reference.requirement != knowledge[key].requirement:
                    raise ValueError(f"Invalid knowledge reference in {report.report_id}.{name}")
        for item in report.items:
            # 证据必须属于当前申请，防止报告展示其他企业的材料。
            for evidence in item.evidence:
                material = materials.get(evidence.material_id)
                if material is None or material.application_id != report.application_id:
                    raise ValueError(f"Invalid material reference in {item.item_id}")
                if evidence.file_name != material.file_name:
                    raise ValueError(f"Mismatched evidence filename in {item.item_id}")
            if item.knowledge_ref:
                key = (item.knowledge_ref.knowledge_id, item.knowledge_ref.version)
                if key not in knowledge:
                    raise ValueError(f"Unknown knowledge reference in {item.item_id}")
                if item.knowledge_ref.requirement != knowledge[key].requirement:
                    raise ValueError(f"Mismatched knowledge requirement in {item.item_id}")

    return data


class SeedRepository:
    """为 API 提供只读查询；后续可替换为 MySQL 实现。"""

    def __init__(self, data: SeedData) -> None:
        self.data = data
        self.enterprises = {item.enterprise_id: item for item in data.enterprises}
        self.applications = {item.application_id: item for item in data.applications}

    def list_enterprises(self) -> list[Enterprise]:
        """列出所有虚构企业客户。"""

        return self.data.enterprises

    def list_applications(self) -> list[ApplicationSummary]:
        """返回申请摘要，并附上每笔申请最近一次预审的处理状态。"""

        latest_reports: dict[str, Report] = {}
        for report in self.data.reports:
            current = latest_reports.get(report.application_id)
            # 解析带时区的时间，避免不同 UTC 偏移下直接比较字符串出错。
            report_time = datetime.fromisoformat(report.generated_at)
            current_time = datetime.fromisoformat(current.generated_at) if current else None
            if current_time is None or report_time > current_time:
                latest_reports[report.application_id] = report

        summaries = []
        for application in self.data.applications:
            latest_report = latest_reports.get(application.application_id)
            summaries.append(
                ApplicationSummary(
                    **application.model_dump(),
                    enterprise_name=self.enterprises[application.enterprise_id].enterprise_name,
                    report_status=latest_report.analysis_status if latest_report else None,
                )
            )
        return summaries

    def get_application(self, application_id: str) -> ApplicationDetail | None:
        """按申请 ID 汇集所属企业、材料和历次报告。"""

        application = self.applications.get(application_id)
        if application is None:
            return None
        return ApplicationDetail(
            application=application,
            enterprise=self.enterprises[application.enterprise_id],
            status_history=sorted(
                (
                    event
                    for event in self.data.status_events
                    if event.application_id == application_id
                ),
                key=lambda event: datetime.fromisoformat(event.occurred_at),
            ),
            materials=[
                material
                for material in self.data.materials
                if material.application_id == application_id
            ],
            reports=[
                report
                for report in self.data.reports
                if report.application_id == application_id
            ],
        )
