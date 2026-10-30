"""HTTP、CLI和Agent共用的只读预审服务，不依赖FastAPI。"""
from app.schemas.materials import CheckRequest
from app.observability.events import record_run


def check_materials(detail, options: CheckRequest | None = None):
    from app.workflows.materials import MaterialWorkflow
    from app.workflows.material_adapter import adapt_application
    options = options or CheckRequest()
    workflow = MaterialWorkflow()
    data = adapt_application(detail, options, workflow.rules['products'])
    result = workflow.run(data, options.use_model)
    record_run('materials.check', result)
    return result


def check_risks(detail, options: CheckRequest | None = None):
    from app.workflows.risk import run_risk_precheck
    result = run_risk_precheck(detail, options or CheckRequest())
    record_run('risk.precheck', result)
    return result
