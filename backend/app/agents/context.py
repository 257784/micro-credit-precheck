"""演示身份由服务端固定注入；不是生产身份认证。"""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RequestContext:
    actor: str
    role: str
    allowed_applications: frozenset[str]
    conversation_id: str
    request_id: str
    run_id: str


def teaching_context(conversation_id, request_id, run_id):
    admin = os.getenv('CREDIT_DEMO_ADMIN') == '1'
    return RequestContext('TEACHING-ADMIN' if admin else 'TEACHING-MANAGER', 'demo_admin' if admin else 'customer_manager',
        frozenset(f'APP-FICT-{i:03}' for i in range(1, 11)), conversation_id, request_id, run_id)
