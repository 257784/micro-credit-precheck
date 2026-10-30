"""DeepSeek 非流式工具决策；SSE 只发送已经校验的结果。"""
import httpx
from app.llm.deepseek import GenerationError, Settings
from app.llm.streaming import check_status


class ToolClient:
    async def complete(self, messages, tools):
        settings = Settings.from_environment()
        payload = {'model': settings.model, 'messages': messages, 'tools': tools,
            'tool_choice': 'auto', 'stream': False, 'thinking': {'type': 'disabled'}, 'max_tokens': 2000}
        try:
            async with httpx.AsyncClient(timeout=min(settings.timeout, 60), follow_redirects=False) as client:
                async with client.stream('POST', 'https://api.deepseek.com/chat/completions',
                    headers={'Authorization': 'Bearer ' + settings.credential}, json=payload) as response:
                    check_status(response.status_code)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 1024 * 1024:
                            raise GenerationError('invalid_response', '模型响应过大。')
            import json
            choice = json.loads(body)['choices'][0]
            message = choice['message']
            if choice.get('finish_reason') not in ('stop', 'tool_calls') or not isinstance(message, dict):
                raise ValueError()
            return message
        except httpx.TimeoutException:
            raise GenerationError('timeout', '模型服务超时，请稍后重试。') from None
        except httpx.HTTPError:
            raise GenerationError('network_error', '模型连接失败，请稍后重试。') from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise GenerationError('invalid_response', '模型响应格式错误。') from None
