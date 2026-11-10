import React, { useEffect, useRef, useState } from 'react';

export default function RiskPrecheck({ applicationId, role, onSaved }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [useModel, setUseModel] = useState(false);
  const active = useRef(null);
  useEffect(() => () => active.current?.abort(), [applicationId]);
  async function run() {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setResult(null); setError(''); setLoading(true);
    try {
      const response = await fetch('/api/applications/' + encodeURIComponent(applicationId) + '/risk-precheck', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_model: useModel }), signal: controller.signal,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(typeof body?.detail === 'string' ? body.detail : '风险预审失败（' + response.status + '），请检查后重试。');
      }
      const value = await response.json();
      if (!controller.signal.aborted) { setResult(value); if (value.saved_report_id) onSaved(); }
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message || '风险预审失败，请重试。');
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  return <section className="review-item" aria-label="风险预审运行">
    <h3>运行风险预审</h3>
    <p>仅供教学和人工核验，不作授信决定。{role === 'risk_reviewer' ? '风控运行后自动保存报告。' : '客户经理运行仅作为临时预览。'}</p>
    <p>自动使用企业声明和材料检查结果；候选事实需人工核实。</p>
    <label><input type="checkbox" checked={useModel} onChange={(event) => setUseModel(event.target.checked)} /> 启用 AI 辅助（调用 DeepSeek，可能产生费用）</label>
    <button type="button" onClick={run} disabled={loading}>{loading ? '预审运行中…' : '运行风险预审'}</button>
    {error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite">
      <p>{result.saved_report_id ? '已保存报告：' + result.saved_report_id : '本次为临时预览，未保存报告。'}</p>
      <p>运行：{result.run_status} · 检索：{result.retrieval_status} · 模型：{result.model_status}</p>
      {Object.entries(result.conditions || {}).filter(([, fact]) => fact?.value != null).map(([key, fact]) => <p key={key}>已使用{key === 'is_used_equipment' ? '设备是否为二手' : '是否以订单或合同为依据'}：{fact.value ? '是' : '否'} · 来源：{fact.location}</p>)}
      {(result.condition_candidates || []).map((item, index) => <p key={index}>材料候选（待核实）：{item.quote} · 材料 {item.material_id} 第 {item.version} 版 · {item.location}</p>)}
      {(result.condition_conflicts || []).length > 0 && <p role="alert">材料候选与企业声明冲突，请人工确认。</p>}
      {result.limitations.map((item, index) => <p key={index}>{item}</p>)}
      <h4>风险线索与人工复核事项</h4>
      {!result.risk_items.length && <p>本次没有形成线索，仍需人工核实，不代表无风险。</p>}
      {result.risk_items.map((item) => <article key={item.item_id}>
        <p>{item.description}（{item.origin === 'rule' ? '规则' : 'AI 辅助'}）</p>
        {item.material_id && <p>材料：{item.material_id} · 第 {item.version_no} 版 {item.evidence_location || ''}</p>}
        {(item.evidence || []).map((evidence, index) => <p key={index}>证据：{evidence.material_id || evidence.source} · {evidence.location}：“{evidence.quote}”</p>)}
        {item.policy_ref && <p>政策依据：{item.policy_ref.join(' · ')}</p>}
        <p>人工操作：{item.suggested_human_action}</p>
      </article>)}
      <h4>缺失或未核验的信息</h4>
      {result.missing_info.map((item, index) => <p key={index}>{item.message || item.description}</p>)}
      <h4>人工复核事项</h4>
      {result.human_review_items.map((item, index) => <p key={index}>{item.item_id}：{item.action}</p>)}
      <details><summary>节点执行轨迹</summary>{result.node_trace.map((node, index) => <p key={index}>{node.node_id}：{node.status} {node.branch || ''}</p>)}</details>
    </div>}
  </section>;
}
