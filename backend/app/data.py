from pathlib import Path

from .models import ApplicationDetail, ApplicationSummary, SeedData

SEED_PATH = Path(__file__).resolve().parents[2] / "mock_data" / "seed.json"


def load_seed(path: Path = SEED_PATH) -> SeedData:
    data = SeedData.model_validate_json(path.read_text(encoding="utf-8"))
    enterprises = {item.enterprise_id: item for item in data.enterprises}
    applications = {item.application_id: item for item in data.applications}
    materials = {item.material_id: item for item in data.materials}
    knowledge = {
        (item.knowledge_id, item.version): item for item in data.knowledge_items
    }

    for label, items, ids in (
        ("enterprise", data.enterprises, enterprises),
        ("application", data.applications, applications),
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
    for material in data.materials:
        if material.application_id not in applications:
            raise ValueError(f"Unknown application for {material.material_id}")
    for report in data.reports:
        if report.application_id not in applications:
            raise ValueError(f"Unknown application for {report.report_id}")
        for item in report.items:
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
    def __init__(self, data: SeedData):
        self.data = data
        self.enterprises = {item.enterprise_id: item for item in data.enterprises}
        self.applications = {item.application_id: item for item in data.applications}

    def list_applications(self) -> list[ApplicationSummary]:
        latest_reports = {}
        for report in self.data.reports:
            current = latest_reports.get(report.application_id)
            if current is None or report.generated_at > current.generated_at:
                latest_reports[report.application_id] = report
        return [
            ApplicationSummary(
                **application.model_dump(),
                enterprise_name=self.enterprises[application.enterprise_id].enterprise_name,
                report_status=(
                    latest_reports[application.application_id].analysis_status
                    if application.application_id in latest_reports
                    else None
                ),
            )
            for application in self.data.applications
        ]

    def get_application(self, application_id: str) -> ApplicationDetail | None:
        application = self.applications.get(application_id)
        if application is None:
            return None
        return ApplicationDetail(
            application=application,
            enterprise=self.enterprises[application.enterprise_id],
            materials=[m for m in self.data.materials if m.application_id == application_id],
            reports=[r for r in self.data.reports if r.application_id == application_id],
        )
