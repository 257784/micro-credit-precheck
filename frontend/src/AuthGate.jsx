import React, { useEffect, useState } from 'react';
import App from './App.jsx';
import AdminPage from './AdminPage.jsx';

export default function AuthGate() {
  const [principal, setPrincipal] = useState(null);
  const [checking, setChecking] = useState(true);
  const [username, setUsername] = useState('');
  const [credential, setCredential] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { fetch('/api/auth/me').then((r) => r.ok ? r.json() : null).then(setPrincipal)
    .catch(() => setError('无法连接服务，请检查后端。')).finally(() => setChecking(false)); }, []);
  async function login(event) {
    event.preventDefault(); setError('');
    try {
      const response = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, credential }) });
      if (!response.ok) throw new Error('登录失败，请检查账号或后端服务。');
      setPrincipal(await response.json()); setCredential('');
    } catch (failure) { setError(failure.message); }
  }
  async function logout() {
    try {
      const response = await fetch('/api/auth/logout', { method: 'POST' });
      if (!response.ok) throw new Error('退出失败，请重试。');
      setPrincipal(null); setCredential('');
    } catch (failure) { setError(failure.message); }
  }
  if (checking) return <p role="status">正在检查登录状态…</p>;
  if (principal) return principal.role === 'admin'
    ? <AdminPage principal={principal} onLogout={logout} />
    : <App key={principal.user_id} principal={principal} onLogout={logout} />;
  return <main className="page"><section className="panel"><h1>登录小微授信系统</h1><p>请使用本机创建的教学账号登录。</p>
    {error && <p role="alert">{error}</p>}<form className="enterprise-form" onSubmit={login}>
      <label>账号<input autoComplete="username" required value={username} onChange={(e) => setUsername(e.target.value)} /></label>
      <label>密码<input type="password" autoComplete="current-password" required value={credential} onChange={(e) => setCredential(e.target.value)} /></label>
      <div className="wide"><button type="submit">登录</button></div></form></section></main>;
}
