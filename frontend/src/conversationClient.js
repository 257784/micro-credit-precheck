// POST 流式协议：以完整 SSE 事件为边界，不能把网络 chunk 当作一条消息。
export async function conversationJson(path, options = {}) {
  let response;
  try {
    response = await fetch('/api/policy/conversations' + path, options);
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('对话连接失败，请检查后端服务。');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const reason = typeof body?.detail === 'string' ? body.detail : '请稍后重试。';
    const error = new Error(reason);
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

export function createSseParser(onEvent) {
  let buffer = '';
  return {
    feed(text) {
      buffer += text;
      if (buffer.length > 1024 * 1024) throw new Error('事件过长，连接已停止。');
      // 兼容 CRLF 被拆在两次读取中的情况，保留末尾未完整的 CR。
      buffer = buffer.replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        let event = 'message';
        const data = [];
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim();
          if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
        }
        if (data.length) onEvent(event, JSON.parse(data.join('\n')));
      }
    },
  };
}

export async function streamConversation(cid, payload, onEvent, signal) {
  const response = await fetch('/api/policy/conversations/' + encodeURIComponent(cid) + '/messages/stream', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload), signal,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = new Error(typeof body?.detail === 'string' ? body.detail : '对话请求失败，请重试。');
    error.status = response.status;
    throw error;
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new Error('服务未返回对话流。');
  }
  let sequence = 0;
  let messageId = null;
  let terminal = false;
  let streamError = null;
  const parser = createSseParser((event, data) => {
    if (data.conversation_id !== cid || data.request_id !== payload.request_id) return;
    if (messageId && data.message_id !== messageId) throw new Error('消息编号不一致。');
    if (!Number.isInteger(data.seq) || data.seq <= 0) throw new Error('事件序号无效。');
    if (data.seq <= sequence) return;
    if (data.seq !== sequence + 1) throw new Error('事件不完整，请恢复对话后重试。');
    if (terminal) throw new Error('终态之后收到额外事件。');
    messageId = data.message_id;
    sequence = data.seq;
    onEvent(event, data);
    if (event === 'done') terminal = true;
    if (event === 'error') {
      terminal = true;
      streamError = new Error(data.message || '本轮未完成，请重试。');
    }
  });
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        parser.feed(decoder.decode());
        break;
      }
      parser.feed(decoder.decode(value, { stream: true }));
    }
    if (streamError) throw streamError;
    if (!terminal) throw new Error('连接在回答完成前中断，请重试或恢复对话。');
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function applyConversationEvent(turn, event, data) {
  const next = { ...turn, message_id: data.message_id || turn.message_id };
  if (event === 'status') next.stage = data.message;
  if (event === 'scope') next.scope = data.label;
  if (event === 'sources') next.sources = data.sources;
  if (event === 'clarification') next.clarification = data.question;
  if (event === 'statement') {
    const statements = [...(turn.statements ?? [])];
    statements[data.statement_index] = data.statement;
    next.statements = statements;
  }
  if (event === 'done') {
    next.status = 'complete';
    next.response = data.response;
    next.statements = [];
    next.clarification = null;
  }
  if (event === 'error') {
    next.status = 'failed';
    next.error = data.message;
    next.statements = [];
    next.clarification = null;
  }
  return next;
}
