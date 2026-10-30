import React, { useEffect, useRef, useState } from 'react';
import { applyConversationEvent, conversationJson, streamConversation } from './conversationClient.js';

const statusLabels = {
  answered: '政策解释',
  insufficient_evidence: '依据不足',
  needs_clarification: '需要补充信息',
  out_of_scope: '超出问答职责',
  configuration_error: '服务尚未配置',
  retrieval_error: '检索失败',
  generation_error: '回答生成失败',
};

export function PolicyAnswer({ response, loading = false, error = '', messageId = '' }) {
  if (loading) return <p role="status">正在检索政策并生成回答，请稍候…</p>;
  if (error) return <p role="alert">{error} 请检查连接后重新提问。</p>;
  if (!response) return <p className="empty-state">输入问题，回答将列出政策依据。</p>;
  return (
    <section className="policy-answer" aria-live="polite">
      <h3>{statusLabels[response.status] ?? '问答结果'}</h3>
      <p className="policy-answer-text">{response.answer}</p>
      {response.missing_information?.length > 0 && (
        <div><h4>待补充信息</h4><ul>{response.missing_information.map((item, index) => (
          <li key={index}>{item}</li>
        ))}</ul></div>
      )}
      {response.warnings?.map((warning, index) => <p role="status" key={index}>{warning}</p>)}
      {response.statements?.length > 0 && (
        <div className="policy-evidence"><h4>回答原文依据</h4>
          {response.statements.map((statement, index) => (
            <div key={index}><p>{statement.text}</p>
              {statement.evidence.map((evidence, evidenceIndex) => (
                <blockquote key={evidenceIndex}>
                  <a href={'#policy-' + messageId + evidence.source_id}>[{evidence.source_id}]</a> {evidence.quote}
                </blockquote>
              ))}
            </div>
          ))}
        </div>
      )}
      <h4>本次检索条款</h4>
      {response.sources?.length ? response.sources.map((source) => (
        <details id={'policy-' + messageId + source.source_id} key={source.source_id}>
          <summary>[{source.source_id}] {source.document_id} · {source.version} · {source.clause}
            {response.cited_source_ids?.includes(source.source_id) ? '（已引用）' : '（候选）'}
          </summary>
          <p>{source.title} · {source.source_path}:{source.source_line}</p>
          <pre>{source.text}</pre>
        </details>
      )) : <p>本次没有可展示的政策条款。</p>}
      <p className="policy-notice">{response.notice}</p>
    </section>
  );
}

export default function PolicyQa({ sessionKey = 'policy-conversation' }) {
  const [question, setQuestion] = useState('');
  const [turns, setTurns] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [scope, setScope] = useState('');
  const requestRef = useRef(null);
  const sessionRef = useRef(null);
  const epoch = useRef(0);

  const restore = async () => {
    const saved = window.sessionStorage.getItem(sessionKey);
    if (!saved) return;
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    const version = epoch.current;
    setLoading(true);
    try {
      const session = await conversationJson('/' + saved, { signal: controller.signal });
      if (!controller.signal.aborted && epoch.current === version) {
        sessionRef.current = saved;
        setTurns(session.turns);
        setError('');
        if (session.turns.some((turn) => turn.status === 'running')) {
          setError('上轮仍在结束中，请稍后点击恢复对话。');
        }
      }
    } catch (failure) {
      if (!controller.signal.aborted && epoch.current === version) {
        setError(failure.message);
        if (failure.status === 404) {
          sessionRef.current = null;
          window.sessionStorage.removeItem(sessionKey);
        }
      }
    } finally {
      if (!controller.signal.aborted && epoch.current === version) setLoading(false);
    }
  };

  useEffect(() => {
    restore();
    return () => { epoch.current += 1; requestRef.current?.abort(); };
  }, []);

  const stop = () => {
    requestRef.current?.abort();
    requestRef.current = null;
    setLoading(false);
    setTurns((items) => items.map((turn) => turn.status === 'running'
      ? { ...turn, status: 'stopped', statements: [], clarification: null, error: '已停止，本轮未完成。' } : turn));
  };

  const startNew = () => {
    epoch.current += 1;
    stop();
    const previous = sessionRef.current;
    sessionRef.current = null;
    window.sessionStorage.removeItem(sessionKey);
    setTurns([]);
    setScope('');
    setError('');
    if (previous) conversationJson('/' + previous, { method: 'DELETE' }).catch(() => {});
  };

  const send = async (text, previousTurn = null) => {
    if (!text.trim() || loading) return;
    const controller = new AbortController();
    requestRef.current = controller;
    const version = epoch.current;
    const rid = crypto.randomUUID();
    let cid = sessionRef.current;
    setLoading(true);
    setQuestion('');
    setError('');
    setTurns((items) => [...items, { request_id: rid, question: text, status: 'running', statements: [], sources: [] }]);
    const current = () => !controller.signal.aborted && version === epoch.current;
    const update = (operation) => {
      if (current()) setTurns((items) => items.map((turn) => turn.request_id === rid ? operation(turn) : turn));
    };
    try {
      if (!cid) {
        const created = await conversationJson('', { method: 'POST', signal: controller.signal });
        cid = created.conversation_id;
        if (!current()) {
          conversationJson('/' + cid, { method: 'DELETE' }).catch(() => {});
          return;
        }
        sessionRef.current = cid;
        window.sessionStorage.setItem(sessionKey, cid);
      }
      await streamConversation(cid, {
        question: text, request_id: rid,
        ...(previousTurn?.message_id ? { retry_of: previousTurn.request_id } : {}),
      }, (event, data) => {
        if (!current()) return;
        if (event === 'scope') setScope(data.label);
        update((turn) => applyConversationEvent(turn, event, data));
      }, controller.signal);
    } catch (failure) {
      if (current()) {
        update((turn) => turn.status === 'complete' ? turn : {
          ...turn, status: 'failed', statements: [], clarification: null,
          error: failure.message || '连接中断，请恢复对话后重试。',
        });
        if (failure.status === 404) {
          sessionRef.current = null;
          window.sessionStorage.removeItem(sessionKey);
        }
      }
    } finally {
      if (current()) setLoading(false);
    }
  };

  return (
    <section className={'policy-page' + (turns.length ? ' has-messages' : '')} aria-label="政策问答">
      <header className="policy-chat-header">
        <div><span className="policy-brand-icon" aria-hidden="true">✦</span><strong>政策问答助手</strong></div>
        <div className="conversation-actions">
          <button type="button" onClick={startNew}>＋ 新对话</button>
          <button type="button" onClick={restore} disabled={loading}>恢复对话</button>
        </div>
      </header>
      <div className="policy-chat-body">
      {scope && <p className="policy-scope">当前解释范围：{scope}，用途变化时可以直接告诉我。</p>}
      {error && <p className="policy-chat-error" role="alert">{error}</p>}
      {!turns.length && <div className="policy-welcome"><span className="policy-welcome-icon" aria-hidden="true">✦</span><h2>你好，想了解什么授信政策？</h2><p>描述你的经营需求或材料问题，我会根据教学政策解答。</p></div>}
      <div className="conversation-messages" aria-label="对话消息">
        {turns.map((turn) => (
          <article key={turn.request_id} className="conversation-turn">
            <div className="user-message"><strong>你</strong><p>{turn.question}</p></div>
            <div className="assistant-message"><strong>政策助手</strong>
              {turn.status === 'complete' ? <PolicyAnswer response={turn.response} messageId={turn.message_id + '-'} /> : (
                <div aria-live="polite">
                  {turn.status === 'running' ? <>
                    <p role="status">{turn.stage || '正在连接…'}</p>
                    <p className="policy-notice">以下要点已核对引用，本轮完整回答尚未完成。</p>
                    {turn.statements?.filter(Boolean).map((statement, index) => (
                      <div key={index}><p>{statement.text}</p>
                        {statement.evidence.map((evidence, i) => <blockquote key={i}>[{evidence.source_id}] {evidence.quote}</blockquote>)}
                      </div>
                    ))}
                    {turn.clarification && <p>{turn.clarification}</p>}
                  </> : <>
                    <p role="alert">{turn.error || '本轮未完成。'} 未完成的正文已撤回。</p>
                    <button type="button" disabled={loading} onClick={() => send(turn.question, turn)}>重试此问题</button>
                  </>}
                  {!!turn.sources?.length && <details><summary>查看本轮候选条款</summary>
                    {turn.sources.map((source) => <p key={source.source_id}>[{source.source_id}] {source.document_id} {source.clause}：{source.text}</p>)}
                  </details>}
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
      <div className="policy-composer-wrap">
        <form className="policy-composer" onSubmit={(event) => { event.preventDefault(); send(question.trim()); }}>
          <label className="policy-input-label" htmlFor="policy-question">你的问题</label>
          <textarea id="policy-question" value={question} rows={3} maxLength={2000} required
            placeholder="向政策助手提问，例如：没有采购合同可以提供报价单吗？"
            onChange={(event) => setQuestion(event.target.value)} />
          <div className="policy-composer-bottom"><span>虚构教学政策 · 信息不足时会追问</span>
            {loading ? <button className="policy-stop" type="button" onClick={stop}>停止生成</button> :
              <button className="policy-send" type="submit" disabled={!question.trim()} aria-label="发送问题">↑</button>}
          </div>
        </form>
        <p className="policy-chat-disclaimer">回答仅供教学参考，不构成授信、审批或放款决定。</p>
      </div>
      </div>
    </section>
  );
}
