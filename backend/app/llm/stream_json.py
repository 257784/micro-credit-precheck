"""有界增量 JSON：完整要点即可校验，最终再严格校验整份对象。"""

import json

from app.llm.deepseek import GenerationError


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("重复 JSON 字段")
        result[key] = value
    return result


class StatementParser:
    """解析顶层对象及 statements 数组，不按花括号正则拆分字符串。"""

    def __init__(self) -> None:
        self.buffer = ""
        self.position = 0
        self.phase = "open"
        self.key = None
        self.statements = []
        self.decoder = json.JSONDecoder(object_pairs_hook=unique_object)

    def feed(self, text: str) -> list[dict]:
        self.buffer += text
        if len(self.buffer.encode("utf-8")) > 1024 * 1024:
            raise GenerationError("invalid_answer", "模型回答超过长度限制。")
        ready = []
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position].isspace():
                self.position += 1
            if self.position >= len(self.buffer):
                return ready
            char = self.buffer[self.position]
            if self.phase in ("open", "colon", "array"):
                expected = {"open": "{", "colon": ":", "array": "["}[self.phase]
                if char != expected:
                    raise GenerationError("invalid_answer", "模型流不是约定的 JSON 对象。")
                self.position += 1
                self.phase = {"open": "key", "colon": "array" if self.key == "statements" else "value",
                              "array": "item"}[self.phase]
            elif self.phase in ("key", "value", "item"):
                if self.phase == "key" and char == "}":
                    self.phase = "end"
                    self.position += 1
                    continue
                if self.phase == "item" and char == "]":
                    self.phase = "separator"
                    self.position += 1
                    continue
                try:
                    value, end = self.decoder.raw_decode(self.buffer, self.position)
                except json.JSONDecodeError:
                    return ready
                except ValueError:
                    raise GenerationError("invalid_answer", "模型 JSON 出现重复字段。") from None
                if self.phase == "key":
                    if not isinstance(value, str):
                        raise GenerationError("invalid_answer", "模型字段名无效。")
                    self.key, self.phase = value, "colon"
                elif self.phase == "item":
                    if not isinstance(value, dict):
                        raise GenerationError("invalid_answer", "回答要点结构错误。")
                    self.statements.append(value)
                    ready.append(value)
                    self.phase = "item_separator"
                else:
                    self.phase = "separator"
                self.position = end
            elif self.phase in ("separator", "item_separator"):
                if char == ",":
                    self.position += 1
                    self.phase = "key" if self.phase == "separator" else "item"
                elif char == ("}" if self.phase == "separator" else "]"):
                    self.position += 1
                    self.phase = "end" if self.phase == "separator" else "separator"
                else:
                    raise GenerationError("invalid_answer", "模型 JSON 分隔符错误。")
            else:
                raise GenerationError("invalid_answer", "模型回答存在额外内容。")

    def finish(self) -> dict:
        try:
            result = json.loads(self.buffer, object_pairs_hook=unique_object)
        except (ValueError, TypeError):
            raise GenerationError("invalid_answer", "模型未返回完整、唯一字段的 JSON。") from None
        if not isinstance(result, dict) or result.get("statements") != self.statements:
            raise GenerationError("invalid_answer", "流式要点与最终回答不一致。")
        return result
