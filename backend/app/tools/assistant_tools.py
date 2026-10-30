"""只读工具调度：参数、服务端申请范围和审计均在执行前检查。"""
import json
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.observability.assistant_audit import AuditStore
from app.schemas.materials import CheckRequest
from app.services.documents import DocumentService
from app.services.prechecks import check_materials, check_risks


class ApplicationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    application_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=1000)
    product: str | None = None


class ToolExecutor:
    definitions = {
        'get_application': ('读取申请状态和基本信息', ApplicationInput),
        'list_materials': ('查看上传材料类别、版本及解析状态', ApplicationInput),
        'check_materials': ('运行材料完整性检查', ApplicationInput),
        'run_risk_precheck': ('运行规则风险预审，不调用额外模型', ApplicationInput),
        'search_policy': ('检索教学政策，当前可能不可用', PolicyInput),
    }

    def __init__(self, application_service, audit=None):
        self.application_service = application_service
        self.audit = audit or AuditStore()

    def schemas(self):
        return [{'type': 'function', 'function': {'name': name, 'description': description,
                'parameters': schema.model_json_schema()}}
                for name, (description, schema) in self.definitions.items()]

    def reject(self, context, name, call_id, reason):
        """记录在执行前被循环预算或协议检查拒绝的请求。"""
        try:
            event = self.audit.begin(context, name[:80], None, call_id[:100])
            self.audit.finish(event, 'failed', reason, 0)
        except Exception:
            raise RuntimeError('audit_unavailable') from None

    def execute(self, context, name, raw, call_id, conditions=None):
        started = monotonic()
        args, target, reason, result = None, None, None, None
        try:
            if len(raw.encode('utf-8')) > 8192:
                raise ValueError('oversized')
            candidate = json.loads(raw)
            if not isinstance(candidate, dict):
                raise ValueError('invalid_arguments')
            possible = candidate.get('application_id')
            if isinstance(possible, str) and len(possible) <= 100:
                target = possible
        except (ValueError, TypeError):
            reason = 'invalid_arguments'
        try:
            event = self.audit.begin(context, name, target, call_id)
        except Exception:
            return {'status': 'audit_unavailable', 'message': '审计不可用，工具未执行。'}
        try:
            if reason:
                result = {'status': 'invalid_arguments'}
            elif name not in self.definitions:
                reason, result = 'unknown_tool', {'status': 'unknown_tool'}
            else:
                try:
                    args = self.definitions[name][1].model_validate(candidate)
                except ValidationError:
                    reason, result = 'invalid_arguments', {'status': 'invalid_arguments'}
                if args is not None and name != 'search_policy':
                    target = args.application_id
                    if target not in context.allowed_applications:
                        reason, result = 'unauthorized', {'status': 'not_accessible', 'message': '申请不可访问。'}
                    else:
                        detail = self.application_service.get_application(target)
                        if detail is None:
                            reason, result = 'not_found', {'status': 'not_accessible', 'message': '申请不可访问。'}
                        elif name == 'get_application':
                            result = {'status': 'ok', 'application': detail.application.model_dump(),
                                      'enterprise_name': detail.enterprise.enterprise_name}
                        elif name == 'list_materials':
                            docs = DocumentService().list(target)
                            result = {'status': 'ok', 'application_id': target, 'materials': [
                                {'id': d['id'], 'category': d['category'], 'version': d['version'],
                                 'filename': d['filename'], 'parse_status': d['parsed']['status']} for d in docs]}
                        else:
                            options = CheckRequest.model_validate({'use_model': False, 'conditions': conditions or {}})
                            workflow = check_materials(detail, options) if name == 'check_materials' else check_risks(detail, options)
                            result = {'status': 'ok', 'application_id': target, 'workflow': workflow}
                elif args is not None:
                    if args.product not in ('equipment', 'working_capital'):
                        reason, result = 'needs_clarification', {'status': 'needs_clarification',
                            'message': '请确认需要查询的教学产品。'}
                    else:
                        try:
                            from app.services.policy import retrieve_candidates, make_sources
                            sources = make_sources(retrieve_candidates(args.question, args.product))
                            result = {'status': 'ok', 'sources': [s.model_dump() for s in sources]}
                        except Exception:
                            reason, result = 'dependency_unavailable', {'status': 'dependency_unavailable',
                                'message': '政策检索不可用，请人工查阅教学政策。'}
        except Exception:
            reason, result = 'tool_error', {'status': 'tool_error', 'message': '工具执行失败，请稍后重试。'}
        try:
            self.audit.finish(event, 'completed' if result['status'] == 'ok' else 'failed', reason,
                              round((monotonic() - started) * 1000))
        except Exception:
            return {'status': 'audit_unavailable', 'message': '审计记录未完成，本次结果不可用。'}
        return result
