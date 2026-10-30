import React, { useEffect, useRef, useState } from 'react';

export default function MaterialCheck({ applicationId }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [used, setUsed] = useState('unknown');
  const [contract, setContract] = useState('unknown');
  const [useModel, setUseModel] = useState(false);
  const active = useRef(null);
  useEffect(() => () => active.current?.abort(), [applicationId]);

  async function run() {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true); setError(''); setResult(null);
    const fact = (value) => value === 'unknown' ? null : {
      value: value === 'yes', source: 'manual_demo', location: '材料页人工演示声明',
    };
    try {
      const response = await fetch('/api/applications/' + encodeURIComponent(applicationId) + '/materials/check', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ use_model: useModel, conditions: {
          is_used_equipment: fact(used), uses_order_contract: fact(contract),
        } }),
      });
      if (!response.ok) throw new Error('检查失败（' + response.status + '），请重试。');
      const body = await response.json();
      if (!controller.signal.aborted) setResult(body);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message || '检查失败，请重试。');
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  return <section className="review-item" aria-labelledby="check-heading">
    <h3 id="check-heading">材料完整性教学检查</h3>
    <p>按虚构F3清单检查声明提交情况；教学摘录不能代替全文解析和人工核验。</p>
    <label>设备是否为二手（仅设备产品适用）
      <select value={used} onChange={(event) => setUsed(event.target.value)}>
        <option value="unknown">未知</option><option value="yes">是</option><option value="no">否</option>
      </select>
    </label>
    <label>是否以具体订单或合同为用途依据（仅经营周转适用）
      <select value={contract} onChange={(event) => setContract(event.target.value)}>
        <option value="unknown">未知</option><option value="yes">是</option><option value="no">否</option>
      </select>
    </label>
    <label><input type="checkbox" checked={useModel} onChange={(event) => setUseModel(event.target.checked)} /> 启用名称辅助（可能调用模型）</label>
    <button type="button" onClick={run} disabled={loading}>{loading ? '检查中…' : '运行完整性检查'}</button>
    {error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite">
      <p>{result.notice}</p><p>运行状态：{result.run_status} · 规则版本：{result.rules_version}</p>
      {result.warnings.map((item, index) => <p role="status" key={index}>{item}</p>)}
      {result.name_hints.map((hint) => <p key={hint.material_id}>名称候选：{hint.material_id} → {hint.candidate_codes.join('、') || '无'}；{hint.reason}（待人工确认）</p>)}
      {['missing_items', 'abnormal_items', 'pending_items'].map((key) => <div key={key}>
        <h4>{{ missing_items: '确定缺项', abnormal_items: '异常项', pending_items: '待确认项' }[key]}</h4>
        {result[key].length ? <ul>{result[key].map((item, index) => <li key={index}>
          {item.code || item.material_id || item.kind}：{item.message} {item.field || ''} {item.action}
          {item.policy_ref && <small>（{item.policy_ref.join(' · ')}）</small>}
        </li>)}</ul> : <p>本项没有记录。</p>}
      </div>)}
      <details><summary>材料清单与规则依据</summary>{result.checklist.map((item) => <p key={item.code}>
        {item.code} {item.name}：{item.status}；{item.requirement}；{item.policy_ref.join(' · ')}
      </p>)}</details>
      <details><summary>节点执行轨迹</summary>{result.node_trace.map((node) => <p key={node.node_id}>
        {node.node_id} {node.type}：{node.status} {node.branch || ''}
      </p>)}</details>
    </div>}
  </section>;
}
