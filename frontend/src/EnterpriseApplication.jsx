import React, { useEffect, useState } from 'react';
import { getJson, postJson } from './api.js';
import DocumentUpload from './DocumentUpload.jsx';

const empty = { enterprise_name: '', industry: '', registered_region: '', product_type: '经营周转贷（教学产品）', requested_amount: '', purpose: '' };

export default function EnterpriseApplication({ onSubmitted }) {
  const [form, setForm] = useState(empty);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [applications, setApplications] = useState([]);
  const [listError, setListError] = useState('');
  const [selected, setSelected] = useState(null);
  const [condition, setCondition] = useState('unknown');
  const [initialCondition, setInitialCondition] = useState('unknown');
  const [issues, setIssues] = useState([]);
  const [resubmitting, setResubmitting] = useState(false);
  const [history, setHistory] = useState([]);
  const [detail, setDetail] = useState(null);
  async function selectApplication(item) {
    setSelected(item); setCondition('unknown'); setIssues([]); setError(''); setHistory([]); setDetail(null);
    try {
      const base = '/api/applications/' + encodeURIComponent(item.application_id);
      setDetail(await getJson(base, '申请详情'));
      setHistory(await getJson(base + '/material-checks', '检查记录'));
    } catch (failure) { setError(failure.message); }
  }
  async function check() {
    setResubmitting(true); setError('');
    try {
      const base = '/api/applications/' + encodeURIComponent(selected.application_id);
      if (condition !== 'unknown') {
        const key = selected.product_type.startsWith('设备') ? 'is_used_equipment' : 'uses_order_contract';
        await postJson(base + '/conditions', '保存申请声明', 'enterprise', { [key]: condition === 'yes' });
      }
      const result = await postJson(base + '/materials/check', '材料检查', 'enterprise', {});
      setIssues([...result.missing_items, ...result.abnormal_items, ...result.pending_items]);
      setHistory(await getJson(base + '/material-checks', '检查记录'));
    } catch (failure) { setError(failure.message); } finally { setResubmitting(false); }
  }
  async function refresh() {
    try { setApplications(await getJson('/api/applications', '我的申请')); setListError(''); }
    catch (failure) { setListError(failure.message); }
  }
  useEffect(() => { refresh(); }, []);
  const field = (name) => ({ value: form[name], onChange: (event) => setForm({ ...form, [name]: event.target.value }) });
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError('');
    try {
      const conditionKey = form.product_type.startsWith('设备') ? 'is_used_equipment' : 'uses_order_contract';
      const submitted = await postJson('/api/applications', '提交申请', 'enterprise', { ...form, requested_amount: Number(form.requested_amount),
        ...(initialCondition === 'unknown' ? {} : { [conditionKey]: initialCondition === 'yes' }) });
      setResult(submitted); setForm(empty); setInitialCondition('unknown'); onSubmitted(); await refresh();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function resubmit() {
    if (!selected || resubmitting) return;
    setResubmitting(true); setError(''); setIssues([]);
    const key = selected.product_type.startsWith('设备') ? 'is_used_equipment' : 'uses_order_contract';
    const payload = condition === 'unknown' ? {} : { [key]: condition === 'yes' };
    try {
      const response = await fetch('/api/applications/' + encodeURIComponent(selected.application_id) + '/resubmit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) { setIssues(body.detail?.issues || []); throw new Error(body.detail?.message || body.detail || '重新提交失败'); }
      setResult(body); setSelected({ ...selected, status: body.status }); await refresh();
    } catch (failure) { setError(failure.message); } finally { setResubmitting(false); }
  }
  return <section className="panel enterprise-page">
    <p className="eyebrow">01 · ENTERPRISE APPLICATION</p><h2>企业授信申请</h2>
    <p>先保存草稿并上传材料，完成初检后再正式提交。</p>
    {result && <div className="notice" role="status">申请：{result.application_id}。当前状态：{result.status}。</div>}
    {error && <p className="notice" role="alert">{error}</p>}
    <section><h3>我的申请</h3>{listError && <p role="alert">{listError}</p>}
      {!listError && !applications.length && <p>暂无申请。</p>}
      {applications.map((item) => <p key={item.application_id}>{item.application_id} · {item.status} <button type="button" onClick={() => selectApplication(item)}>查看详情</button></p>)}</section>
    {selected && <section><h3>申请材料 · {selected.application_id}</h3>
      {detail && <><p>{detail.enterprise.enterprise_name} · {detail.application.product_type} · {detail.application.requested_amount} 元</p><p>资金用途：{detail.application.purpose}</p>{detail.status_history.map(e => <p key={e.event_id}>{e.occurred_at} · {e.event_label}</p>)}</>}
      <DocumentUpload key={selected.application_id + selected.status} applicationId={selected.application_id} readOnly={!['草稿', '待企业补充材料'].includes(selected.status)} onUploaded={() => selectApplication(selected)} />
      {['草稿', '待企业补充材料'].includes(selected.status) && <><label>{selected.product_type.startsWith('设备') ? '设备是否为二手？' : '是否以具体订单或合同作为用途依据？'}
        <select value={condition} onChange={(event) => setCondition(event.target.value)}><option value="unknown">沿用申请声明或尚未确认</option><option value="yes">是</option><option value="no">否</option></select></label>
        <button type="button" disabled={resubmitting} onClick={check}>运行材料完整性检查</button>
        <button type="button" disabled={resubmitting} onClick={resubmit}>{resubmitting ? '检查中…' : '检查并正式提交'}</button>
        <p>材料名称及正文将进行规则初检，证据是否充分仍由风控人员核验。</p></>}
      {issues.length > 0 && <ul>{issues.map((issue, index) => <li key={index}>{issue.message} {issue.action}</li>)}</ul>}
      <h4>检查记录</h4>{history.map(item => <p key={item.check_id}>{item.checked_at} · {item.stale ? '材料或声明已变化，结果过期' : '当前材料版本'} · {item.result.run_status}</p>)}
    </section>}
    <form onSubmit={submit} className="enterprise-form">
      <label>企业名称<input required maxLength="150" {...field('enterprise_name')} /></label>
      <label>所属行业<input required maxLength="100" {...field('industry')} /></label>
      <label>注册地区<input required maxLength="100" {...field('registered_region')} /></label>
      <label>申请产品<select {...field('product_type')} onChange={(event) => { setForm({ ...form, product_type: event.target.value }); setInitialCondition('unknown'); }}><option>经营周转贷（教学产品）</option><option>设备更新贷（教学产品）</option></select></label>
      <label>{form.product_type.startsWith('设备') ? '设备是否为二手？' : '是否以具体订单或合同作为用途依据？'}<select value={initialCondition} onChange={(event) => setInitialCondition(event.target.value)}><option value="unknown">尚未确认</option><option value="yes">是</option><option value="no">否</option></select></label>
      <label>申请金额（元）<input required type="number" min="1" max="100000000" step="1" {...field('requested_amount')} /></label>
      <label className="wide">资金用途<textarea required maxLength="1000" {...field('purpose')} /></label>
      <div className="wide"><button disabled={busy} type="submit">{busy ? '正在保存…' : '保存申请草稿'}</button></div>
    </form>
  </section>;
}
