"""教学脱敏：仅识别常见中国大陆手机号和 18 位身份证号码。"""
import re

ID_NUMBER = re.compile(r'(?<![0-9A-Za-z])([1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx])(?![0-9A-Za-z])')
PHONE = re.compile(r'(?<![0-9A-Za-z])(1[3-9]\d{9})(?![0-9A-Za-z])')
IDENTIFIER_KEYS = frozenset({'application_id', 'enterprise_id', 'report_id', 'material_id', 'item_id',
    'review_id', 'event_id', 'run_id', 'request_id', 'conversation_id', 'id'})


def redact_text(text, mode='display'):
    if mode not in ('display', 'model'):
        raise ValueError('unknown redaction mode')
    def replace_id(match):
        value = match.group(1)
        return value[:6] + '********' + value[-4:] if mode == 'display' else '[身份证号已隐藏]'
    def replace_phone(match):
        value = match.group(1)
        return value[:3] + '****' + value[-4:] if mode == 'display' else '[手机号已隐藏]'
    return PHONE.sub(replace_phone, ID_NUMBER.sub(replace_id, text))


def redact_value(value, mode='display'):
    if isinstance(value, str):
        return redact_text(value, mode)
    if isinstance(value, list):
        return [redact_value(item, mode) for item in value]
    if isinstance(value, dict):
        return {key: item if key in IDENTIFIER_KEYS else redact_value(item, mode) for key, item in value.items()}
    return value
