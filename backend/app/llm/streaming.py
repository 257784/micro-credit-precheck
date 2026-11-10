"""可取消的 DeepSeek 异步传输；只转发正文，不转发推理过程。"""

import json

import httpx

from app.llm.deepseek import GenerationError, Settings
from app.core.redaction import redact_value


def check_status(status: int) -> None:
    if status in (401, 403):
        raise GenerationError("authentication_failed", "模型认证失败，请检查后端配置。")
    if status == 429:
        raise GenerationError("rate_limited", "模型限流，请稍后重试。")
    if not 200 <= status < 300:
        raise GenerationError("upstream_error", f"模型服务请求失败（HTTP {status}）。")


class AsyncDeepSeek:
    def __init__(self, settings: Settings, transport=None) -> None:
        self.settings = settings
        self.transport = transport

    def _payload(self, messages: list, stream: bool) -> dict:
        return {"model": self.settings.model, "messages": redact_value(messages, 'model'), "stream": stream,
                "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"},
                "temperature": 0, "max_tokens": 4000}

    def _client(self):
        return httpx.AsyncClient(
            headers={"Authorization": "Bearer " + self.settings.credential},
            timeout=httpx.Timeout(self.settings.timeout, connect=min(10, self.settings.timeout)),
            follow_redirects=False, transport=self.transport,
        )

    async def complete(self, messages: list) -> str:
        try:
            async with self._client() as client:
                async with client.stream("POST", "https://api.deepseek.com/chat/completions",
                                         json=self._payload(messages, False)) as response:
                    check_status(response.status_code)
                    parts, size = [], 0
                    async for part in response.aiter_bytes():
                        size += len(part)
                        if size > 1024 * 1024:
                            raise GenerationError("invalid_response", "模型响应过大。")
                        parts.append(part)
            choice = json.loads(b"".join(parts))["choices"][0]
            content = choice["message"]["content"]
            if choice["finish_reason"] != "stop" or not isinstance(content, str) or not content.strip():
                raise ValueError()
            return content
        except httpx.TimeoutException:
            raise GenerationError("timeout", "模型服务超时，请重试。") from None
        except httpx.HTTPError:
            raise GenerationError("network_error", "模型服务连接失败，请重试。") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise GenerationError("invalid_response", "模型响应不完整或格式错误。") from None

    async def stream(self, messages: list):
        finished, ended, size = False, False, 0
        try:
            async with self._client() as client:
                async with client.stream("POST", "https://api.deepseek.com/chat/completions",
                                         json=self._payload(messages, True)) as response:
                    check_status(response.status_code)
                    data = []
                    async for line in response.aiter_lines():
                        size += len(line.encode("utf-8"))
                        if size > 1024 * 1024:
                            raise GenerationError("invalid_response", "模型流超过长度限制。")
                        if line.startswith("data:"):
                            data.append(line[5:].lstrip())
                        elif not line and data:
                            raw = "\n".join(data)
                            data = []
                            if raw == "[DONE]":
                                ended = True
                                break
                            body = json.loads(raw)
                            if not body.get("choices"):
                                continue
                            choice = body["choices"][0]
                            if choice.get("finish_reason"):
                                if choice["finish_reason"] != "stop":
                                    raise GenerationError("invalid_response", "模型回答未完整生成。")
                                finished = True
                            content = choice.get("delta", {}).get("content")
                            if content:
                                if not isinstance(content, str):
                                    raise ValueError()
                                yield content
            if not finished or not ended:
                raise GenerationError("interrupted", "模型流提前结束，请重试。")
        except httpx.TimeoutException:
            raise GenerationError("timeout", "模型服务超时，请重试。") from None
        except httpx.HTTPError:
            raise GenerationError("network_error", "模型连接中断，请重试。") from None
        except (ValueError, TypeError, KeyError, IndexError):
            raise GenerationError("invalid_response", "模型流格式错误。") from None
