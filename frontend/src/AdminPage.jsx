import React, { useEffect, useState } from 'react';

export default function AdminPage({ principal, onLogout }) {
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({ username: '', display_name: '', role: 'enterprise', credential: '' });
  const roles = ['enterprise', 'customer_manager', 'risk_reviewer', 'approver', 'admin'];
  async function fetchJson(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error('读取失败（' + response.status + '）');
    return response.json();
  }
  useEffect(() => { fetchJson('/api/auth/users').then(setUsers).catch(error => setMessage(error.message)); }, []);
  async function loadAudit() { try { setAudit(await fetchJson('/api/credit-assistant/audit')); } catch (error) { setMessage(error.message); } }
  async function save(path, method, payload) {
    try {
      const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '操作失败');
      setUsers(await fetchJson('/api/auth/users')); setMessage('账号信息已更新。'); return true;
    } catch (error) { setMessage(error.message); return false; }
  }
  async function create(event) {
    event.preventDefault();
    if (await save('/api/auth/users', 'POST', form)) setForm({ username: '', display_name: '', role: 'enterprise', credential: '' });
  }
  return <main className="page"><section className="panel"><h1>账号与审计</h1>
    <p>{principal.display_name} · 管理员 <button type="button" onClick={onLogout}>退出登录</button></p>
    <p>申请由系统自动分配；账号变更会撤销受影响的登录会话。</p>
    {message && <p role="status">{message}</p>}
    <h2>创建账号</h2><form onSubmit={create} className="enterprise-form">
      <label>登录名<input required value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} /></label>
      <label>显示名称<input required value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} /></label>
      <label>角色<select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>{roles.map(role => <option key={role}>{role}</option>)}</select></label>
      <label>初始密码<input required type="password" minLength={12} value={form.credential} onChange={e => setForm({ ...form, credential: e.target.value })} /></label>
      <button type="submit">创建账号</button></form>
    <h2>账号列表</h2>{users.map(user => <p key={user.user_id}>{user.display_name} · {user.active ? '启用' : '停用'} {' '}
      <select aria-label={'角色：' + user.display_name} value={user.role} disabled={user.user_id === principal.user_id}
        onChange={e => save('/api/auth/users/' + user.user_id, 'PATCH', { role: e.target.value })}>{roles.map(role => <option key={role}>{role}</option>)}</select>{' '}
      <button type="button" disabled={user.user_id === principal.user_id} onClick={() => save('/api/auth/users/' + user.user_id, 'PATCH', { active: !user.active })}>{user.active ? '停用' : '启用'}</button></p>)}
    <h2>助手工具审计</h2><button type="button" onClick={loadAudit}>读取最近审计记录</button>
    {audit.map(entry => <p key={entry.event_id}>{entry.occurred_at} · {entry.actor} · {entry.application_id || '无申请'} · {entry.tool_name} · {entry.status}</p>)}
  </section></main>;
}
