"""只读工具注册表，由调用方注入申请服务，避免依赖API全局实例。"""
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.materials import CheckRequest
from app.services.prechecks import check_materials, check_risks


class ApplicationToolInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    application_id: str = Field(min_length=1, max_length=100)
    options: CheckRequest = Field(default_factory=CheckRequest)


class ReadOnlyTools:
    """注册表不执行审批；集成Agent时由上层提供已授权的申请服务。"""
    def __init__(self, application_service):
        self.application_service = application_service
        self.registry = {'check_materials': check_materials, 'run_risk_precheck': check_risks}

    def invoke(self, name: str, arguments: dict):
        if name not in self.registry:
            raise ValueError('未注册的只读工具')
        request = ApplicationToolInput.model_validate(arguments)
        detail = self.application_service.get_application(request.application_id)
        if detail is None:
            raise LookupError('申请不存在')
        return self.registry[name](detail, request.options)

    def definitions(self):
        return [{'name': name, 'input_schema': ApplicationToolInput.model_json_schema()}
                for name in self.registry]
