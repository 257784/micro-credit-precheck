import React, { useEffect, useRef, useState } from 'react';

export default function RiskPrecheck({ applicationId }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [useModel, setUseModel] = useState(false);
  const [used, setUsed] = useState('unknown');
  const [contract, setContract] = useState('unknown');
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
        body: JSON.stringify({ use_model: useModel, conditions: {
          is_used_equipment: used === 'unknown' ? null : { value: used === 'yes', source: 'manual_demo', location: '风险预审页人工演示声明' },
          uses_order_contract: contract === 'unknown' ? null : { value: contract === 'yes', source: 'manual_demo', location: '风险预审页人工演示声明' },
        } }), signal: controller.signal,
      });
      if (!response.ok) throw new Error('风险预审失败（' + response.status + '），请检查后重试。');
      const value = await response.json();
      if (!controller.signal.aborted) setResult(value);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message || '风险预审失败，请重试。');
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  return <section className="review-item" aria-label="风险预审运行">
    <h3>运行风险预审</h3>
    <p>仅供教学和人工核验，不作授信决定。结果为临时结果，刷新后需要重新运行。</p>
    <label>设备是否为二手（设备贷）<select value={used} onChange={(event) => setUsed(event.target.value)}><option value="unknown">未知</option><option value="yes">是</option><option value="no">否</option></select></label>
    <label>是否以订单或合同作为用途依据（经营周转贷）<select value={contract} onChange={(event) => setContract(event.target.value)}><option value="unknown">未知</option><option value="yes">是</option><option value="no">否</option></select></label>
    <label><input type="checkbox" checked={useModel} onChange={(event) => setUseModel(event.target.checked)} /> 启用 AI 辅助（调用 DeepSeek，可能产生费用）</label>
    <button type="button" onClick={run} disabled={loading}>{loading ? '预审运行中…' : '运行风险预审'}</button>
    {error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite">
      <p>本次运行结果，尚未纳入原有逐项复核记录。</p>
      <p>运行：{result.run_status} · 检索：{result.retrieval_status} · 模型：{result.model_status}</p>
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
