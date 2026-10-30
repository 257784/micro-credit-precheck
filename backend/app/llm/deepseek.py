"""DeepSeek JSON Chat Completions；不记录凭据、上游错误正文或推理过程。"""

from dataclasses import dataclass, field
from http.client import HTTPException as HTTPTransportError
import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class GenerationError(Exception):
    """安全错误码供页面恢复，不附带上游响应或认证请求信息。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Settings:
    credential: str = field(repr=False)
    model: str = "deepseek-flash"
    timeout: int = 60

    @classmethod
    def from_environment(cls) -> "Settings":
        credential = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not credential:
            raise GenerationError("missing_api_key", "后端未配置 DEEPSEEK_API_KEY，请配置后重启。")
        if "\r" in credential or "\n" in credential:
            raise GenerationError("invalid_config", "模型凭据格式有误，请检查本机配置。")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip()
        try:
            timeout = int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "60"))
        except ValueError:
            raise GenerationError("invalid_config", "DEEPSEEK_TIMEOUT_SECONDS 必须是整数。") from None
        if not model or not 1 <= timeout <= 180:
            raise GenerationError("invalid_config", "请检查模型名或超时设置（1—180 秒）。")
        return cls(credential, model, timeout)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DeepSeekClient:
    """仅调用官方 HTTPS 地址，单次请求不自动重试。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete(self, messages: list[dict]) -> str:
        payload = {
            "model": self.settings.model, "messages": messages,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"}, "stream": False,
            "temperature": 0, "max_tokens": 3000,
        }
        request = Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.settings.credential},
            method="POST",
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=self.settings.timeout) as response:
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise GenerationError("invalid_response", "模型响应过大，请缩短问题后重试。")
            body = json.loads(raw)
            choice = body["choices"][0]
            content = choice["message"]["content"]
            if choice.get("finish_reason") != "stop" or not isinstance(content, str) or not content.strip():
                raise GenerationError("invalid_response", "模型回答为空或未完整生成，请重试。")
            return content
        except HTTPError as error:
            code = error.code
            error.close()
            if code in (401, 403):
                raise GenerationError("authentication_failed", "模型认证失败，请检查后端 API Key。") from None
            if code == 402:
                raise GenerationError("insufficient_balance", "模型账户余额不足，请检查账户。") from None
            if code == 429:
                raise GenerationError("rate_limited", "模型服务限流，请稍后重试。") from None
            raise GenerationError("upstream_error", f"模型服务请求失败（HTTP {code}），请稍后重试。") from None
        except (TimeoutError, socket.timeout):
            raise GenerationError("timeout", "模型服务超时，请稍后重试。") from None
        except URLError:
            raise GenerationError("network_error", "无法连接模型服务，请检查后端网络。") from None
        except (OSError, HTTPTransportError):
            raise GenerationError("network_error", "模型服务连接中断，请稍后重试。") from None
        except (ValueError, KeyError, IndexError, TypeError, UnicodeError):
            raise GenerationError("invalid_response", "模型服务响应格式错误，请重试。") from None
