import React, { useEffect, useRef, useState } from 'react';
import { createSseParser } from './conversationClient.js';
import AssistantResult from './AssistantResult.jsx';

export default function CreditAssistant({ applicationId = null }) {
  const [session, setSession] = useState(null);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [progress, setProgress] = useState([]);
  const [error, setError] = useState('');
  const [running, setRunning] = useState(false);
  const [equipment, setEquipment] = useState('unknown');
  const aborter = useRef(null);
  const failedRequest = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/credit-assistant/conversations', { method: 'POST', signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error('无法创建会话'); return response.json(); })
      .then((data) => setSession(data.conversation_id))
      .catch((e) => { if (e.name !== 'AbortError') setError(e.message); });
    return () => { controller.abort(); aborter.current?.abort(); };
  }, [applicationId]);
  async function send(event) {
    event.preventDefault();
    if (!session || !question.trim() || running) return;
    const current = question.trim();
    setQuestion(''); setError(''); setProgress([]); setRunning(true);
    setMessages((items) => [...items, { role: 'user', text: current }]);
    const controller = new AbortController(); aborter.current = controller;
    let completed = false; let structured = null; let accepted = false;
    const requestId = crypto.randomUUID();
    try {
      const response = await fetch(`/api/credit-assistant/conversations/${session}/messages/stream`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ question: current, application_id: applicationId, request_id: requestId,
          ...(failedRequest.current?.question === current ? { retry_of: failedRequest.current.id } : {}),
          ...(equipment === 'unknown' ? { clear_conditions: true } : { is_used_equipment: equipment === 'used' }) }),
      });
      if (!response.ok || !response.body) throw new Error('助手请求失败，请稍后重试。');
      accepted = true;
      const parser = createSseParser((type, data) => {
        if (type === 'progress') setProgress((items) => [...items, data.message]);
        if (type === 'tool_start') setProgress((items) => [...items, `开始 ${data.tool}`]);
        if (type === 'tool_end') setProgress((items) => [...items, `${data.tool}：${data.status}（${data.duration_ms} ms）`]);
        if (type === 'result') structured = data.result;
        if (type === 'error') throw new Error(data.message);
        if (type === 'done') completed = true;
      });
      const reader = response.body.getReader(); const decoder = new TextDecoder();
      while (true) { const item = await reader.read(); if (item.done) break; parser.feed(decoder.decode(item.value, { stream: true })); }
      parser.feed(decoder.decode());
      if (!completed || !structured || structured.schema_version !== '1.0') throw new Error('连接中断或结果不完整，本轮没有完成。');
      failedRequest.current = null;
      setMessages((items) => [...items, { role: 'assistant', result: structured }]);
    } catch (e) { failedRequest.current = accepted ? { question: current, id: requestId } : null; setError(e.name === 'AbortError' ? '已停止；已开始的只读操作可能仍在结束。' : e.message); }
    finally { setRunning(false); aborter.current = null; }
  }
  return <section className="panel"><h2>客户经理授信助手</h2>
    <p>教学演示身份，仅访问虚构样例；助手不作授信决定。{applicationId && `当前申请：${applicationId}`}</p>
    {messages.map((item, index) => item.role === 'user' ? <p key={index}><strong>你：</strong>{item.text}</p> : <AssistantResult key={index} result={item.result} />)}
    {progress.map((item, index) => <p key={index} role="status">{item}</p>)}
    {error && <p role="alert">{error}</p>}
    <form onSubmit={send}><label>问题<textarea value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={2000} /></label>
      <label>设备情况（人工教学声明）<select value={equipment} onChange={(e) => setEquipment(e.target.value)}>
        <option value="unknown">未确认</option><option value="new">全新设备</option><option value="used">二手设备</option>
      </select></label>
      <button disabled={!session || running || !question.trim()}>发送</button>
      {running && <button type="button" onClick={() => aborter.current?.abort()}>停止</button>}</form>
  </section>;
}
