import React, { useEffect, useState } from 'react';

export default function ClaimApplications({ onClaimed }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  async function refresh() {
    setLoading(true);
    try { const response = await fetch('/api/applications/unassigned'); if (!response.ok) throw new Error('待认领申请读取失败'); setItems(await response.json()); }
    catch (failure) { setError(failure.message); } finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, []);
  async function claim(id) {
    setError('');
    try { const response = await fetch('/api/applications/' + encodeURIComponent(id) + '/claim', { method: 'POST' });
      if (!response.ok) throw new Error(response.status === 409 ? '申请已被认领，请刷新。' : '认领失败。');
      await refresh(); onClaimed();
    } catch (failure) { setError(failure.message); }
  }
  return <section className="panel"><h2>待认领申请</h2><p>认领前仅显示申请编号。</p>
    {loading && <p role="status">正在读取…</p>}{error && <p role="alert">{error}</p>}
    {!loading && !items.length && <p>暂无待认领申请。</p>}
    {items.map((item) => <p key={item.application_id}>{item.application_id} <button type="button" onClick={() => claim(item.application_id)}>认领</button></p>)}
    <button type="button" onClick={refresh}>刷新</button></section>;
}
