"""HTTP、CLI和Agent共用的只读预审服务，不依赖FastAPI。"""
from app.schemas.materials import CheckRequest
from app.observability.events import record_run


def check_materials(detail, options: CheckRequest | None = None):
    from app.workflows.materials import MaterialWorkflow
    from app.workflows.material_adapter import adapt_application
    options = options or CheckRequest()
    from app.services.condition_facts import resolve_conditions
    conditions, candidates, conflicts = resolve_conditions(detail, options.conditions)
    options = options.model_copy(update={'conditions': conditions})
    workflow = MaterialWorkflow()
    data = adapt_application(detail, options, workflow.rules['products'])
    result = workflow.run(data, options.use_model)
    result['condition_candidates'] = candidates
    result['condition_conflicts'] = conflicts
    record_run('materials.check', result)
    return result


def check_risks(detail, options: CheckRequest | None = None):
    from app.workflows.risk import run_risk_precheck
    from app.services.condition_facts import resolve_conditions
    options = options or CheckRequest()
    conditions, candidates, conflicts = resolve_conditions(detail, options.conditions)
    result = run_risk_precheck(detail, options.model_copy(update={'conditions': conditions}))
    result['condition_candidates'] = candidates
    result['condition_conflicts'] = conflicts
    result['conditions'] = conditions.model_dump()
    record_run('risk.precheck', result)
    return result
