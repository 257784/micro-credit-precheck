import React, { useState } from 'react';
import { postJson } from './api.js';

const empty = { enterprise_name: '', industry: '', registered_region: '', product_type: '经营周转贷（教学产品）', requested_amount: '', purpose: '' };

export default function EnterpriseApplication({ onSubmitted }) {
  const [form, setForm] = useState(empty);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const field = (name) => ({ value: form[name], onChange: (event) => setForm({ ...form, [name]: event.target.value }) });
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError('');
    try {
      const submitted = await postJson('/api/applications', '提交申请', 'enterprise', { ...form, requested_amount: Number(form.requested_amount) });
      setResult(submitted); setForm(empty); onSubmitted();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel enterprise-page">
    <p className="eyebrow">01 · ENTERPRISE APPLICATION</p><h2>企业授信申请</h2>
    <p>填写虚构教学企业的信息，提交后等待材料补充和人工核验。</p>
    {result && <div className="notice" role="status">申请已提交：{result.application_id}。当前状态：{result.status}。请保存申请编号，材料需后续补充。</div>}
    {error && <p className="notice" role="alert">{error}</p>}
    <form onSubmit={submit} className="enterprise-form">
      <label>企业名称<input required maxLength="150" {...field('enterprise_name')} /></label>
      <label>所属行业<input required maxLength="100" {...field('industry')} /></label>
      <label>注册地区<input required maxLength="100" {...field('registered_region')} /></label>
      <label>申请产品<select {...field('product_type')}><option>经营周转贷（教学产品）</option><option>设备更新贷（教学产品）</option></select></label>
      <label>申请金额（元）<input required type="number" min="1" max="100000000" step="1" {...field('requested_amount')} /></label>
      <label className="wide">资金用途<textarea required maxLength="1000" {...field('purpose')} /></label>
      <div className="wide"><button disabled={busy} type="submit">{busy ? '正在提交…' : '提交申请'}</button></div>
    </form>
  </section>;
}
