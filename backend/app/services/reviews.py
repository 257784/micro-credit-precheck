from app.repositories.reviews import ReviewConflict, ReviewInputError, STATUS_BY_ACTION
from app.schemas.business import ApplicationDetail, ApplicationSummary, ReviewRecord, ReviewSubmission, StatusEvent
import json
from datetime import datetime

class ReviewService:
    """通过注入的Repository读取申请与复核动作，保持接口返回结构。"""

    def __init__(self, repository, store) -> None:
        self.repository = repository
        self.store = store

    def list_applications(self) -> list[ApplicationSummary]:
        return self.repository.list_applications()

    def get_application(self, application_id: str) -> ApplicationDetail | None:
        detail = self.repository.get_application(application_id)
        if detail is None:
            return None
        # 返回对象与种子模型可能共享引用；合并状态前先复制，保持种子只读。
        detail = detail.model_copy(deep=True)
        actions = self.store.actions_for(application_id)
        for action in actions:
            detail.status_history.append(
                StatusEvent(
                    event_id=action["action_id"],
                    application_id=application_id,
                    event_label=STATUS_BY_ACTION[action["kind"]],
                    occurred_at=action["occurred_at"],
                )
            )
            if action["kind"] != "start":
                detail.reviews.append(
                    ReviewRecord(
                        review_id=action["action_id"],
                        application_id=application_id,
                        report_id=action["report_id"],
                        reviewer_id=action["reviewer_id"],
                        reviewed_at=action["occurred_at"],
                        review_result=action["kind"],
                        review_note=action["review_note"],
                        item_reviews=json.loads(action["item_reviews_json"]),
                    )
                )
        detail.status_history.sort(key=lambda event: datetime.fromisoformat(event.occurred_at))
        return detail

    def start(self, application_id: str, reviewer_id: str) -> ApplicationDetail | None:
        detail = self.repository.get_application(application_id)
        if detail is None:
            return None
        self.store.append(application_id, detail.application.status, "待风控复核", "start", reviewer_id)
        return self.get_application(application_id)

    def submit(
        self, application_id: str, reviewer_id: str, submission: ReviewSubmission
    ) -> ApplicationDetail | None:
        detail = self.repository.get_application(application_id)
        if detail is None:
            return None
        current = self.get_application(application_id)
        if current.application.status != "风控复核中":
            raise ReviewConflict(f"当前状态为“{current.application.status}”，请刷新申请后重试。")
        note = submission.review_note.strip()
        if not note:
            raise ReviewInputError("请填写人工复核意见或补件原因。")
        latest_report = max(
            detail.reports,
            key=lambda report: datetime.fromisoformat(report.generated_at),
            default=None,
        )
        if latest_report and latest_report.workflow_result is not None and submission.report_id != latest_report.report_id:
            raise ReviewConflict('预审报告已更新，请刷新后重新复核。')
        if submission.review_result == "complete" and (
            latest_report is None or latest_report.analysis_status == "failed"
        ):
            raise ReviewInputError("无可用报告或报告处理失败，不能直接完成复核；请核实后要求补件。")
        expected_ids = {item.item_id for item in latest_report.items} if latest_report and latest_report.analysis_status != 'failed' else set()
        submitted_ids = [item.item_id for item in submission.item_reviews]
        if set(submitted_ids) != expected_ids or len(submitted_ids) != len(expected_ids):
            raise ReviewInputError("请逐项确认或修正当前报告的所有关注项。")
        for item in submission.item_reviews:
            if item.decision == "corrected" and not (item.correction_note or "").strip():
                raise ReviewInputError("修正关注项时请填写修正说明。")
        self.store.append(
            application_id,
            detail.application.status,
            "风控复核中",
            submission.review_result,
            reviewer_id,
            latest_report.report_id if latest_report else None,
            note,
            submission.item_reviews,
        )
        return self.get_application(application_id)
