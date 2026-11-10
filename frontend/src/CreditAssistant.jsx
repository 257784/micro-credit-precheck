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
  const [conversationVersion, setConversationVersion] = useState(0);
  const aborter = useRef(null);
  const failedRequest = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/credit-assistant/conversations', { method: 'POST', signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error('无法创建会话'); return response.json(); })
      .then((data) => setSession(data.conversation_id))
      .catch((e) => { if (e.name !== 'AbortError') setError(e.message); });
    return () => { controller.abort(); aborter.current?.abort(); };
  }, [applicationId, conversationVersion]);
  function startNew() {
    setSession(null); setMessages([]); setProgress([]); setError(''); setQuestion('');
    failedRequest.current = null;
    setConversationVersion((value) => value + 1);
  }
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
          ...(failedRequest.current?.question === current ? { retry_of: failedRequest.current.id } : {}) }),
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
  return <section className={'policy-page credit-chat' + (messages.length ? ' has-messages' : '')} aria-label="客户经理授信助手">
    <header className="policy-chat-header"><div><span className="policy-brand-icon" aria-hidden="true">✦</span><strong>客户经理授信助手</strong></div>
      <div className="conversation-actions"><button type="button" disabled={running} onClick={startNew}>＋ 新对话</button></div>
    </header>
    <div className="policy-chat-body">
      {applicationId && <p className="policy-scope">当前申请：{applicationId}</p>}
      {!messages.length && <div className="policy-welcome"><span className="policy-welcome-icon" aria-hidden="true">✦</span>
        <h2>你好，需要我协助处理什么？</h2><p>输入申请编号和问题，我可以协助查看材料、预审线索与政策依据。</p></div>}
      <div className="conversation-messages" aria-label="对话消息">
        {messages.map((item, index) => item.role === 'user' ?
          <div className="conversation-turn" key={index}><div className="user-message"><strong>你</strong><p>{item.text}</p></div></div> :
          <div className="assistant-message" key={index}><AssistantResult result={item.result} /></div>)}
        {running && <div className="assistant-message" aria-live="polite"><strong>授信助手</strong>
          {progress.length ? progress.map((item, index) => <p key={index} role="status">{item}</p>) : <p role="status">正在准备处理…</p>}
        </div>}
        {!running && progress.length > 0 && <details><summary>查看本轮工具进度</summary>{progress.map((item, index) => <p key={index}>{item}</p>)}</details>}
        {error && <p className="policy-chat-error" role="alert">{error}</p>}
      </div>
      <div className="policy-composer-wrap">
        <form className="policy-composer" onSubmit={send}>
          <label className="policy-input-label" htmlFor="credit-question">问题</label>
          <textarea id="credit-question" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={2000}
            placeholder="输入申请编号和问题，例如：这笔申请还缺少哪些材料？" />
          <div className="policy-composer-bottom"><span>信息不足时会在对话中询问。</span>
            {running ? <button className="policy-stop" type="button" onClick={() => aborter.current?.abort()}>停止生成</button> :
              <button className="policy-send" type="submit" disabled={!session || !question.trim()} aria-label="发送问题">↑</button>}
          </div>
        </form>
        <p className="policy-chat-disclaimer">教学演示身份，仅访问虚构样例；助手不作授信决定。</p>
      </div>
    </div>
  </section>;
}
