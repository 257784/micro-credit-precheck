import React, { useEffect, useState } from 'react';
import { getJson, postJson } from './api.js';

export default function ApprovalPage({ applicationId, detail, role, onChanged }) {
  const [note, setNote] = useState('');
  const [records, setRecords] = useState([]);
  const [error, setError] = useState('');
  const base = '/api/applications/' + encodeURIComponent(applicationId);
  async function load() { try { setRecords(await getJson(base + '/approval-records', '审批记录')); } catch (e) { setError(e.message); } }
  useEffect(() => { load(); }, [applicationId]);
  async function act(action) {
    setError('');
    try { await postJson(base + '/approval/' + action, '审批操作', role, action === 'start' ? undefined : { note }); await load(); onChanged(); }
    catch (e) { setError(e.message); }
  }
  return <section className="panel"><h2>审批处理与结果</h2>{error && <p role="alert">{error}</p>}
    {detail && <><p>{detail.enterprise.enterprise_name} · {detail.application.application_id} · {detail.application.status}</p>
      {role === 'approver' && detail.application.status === '待审批' && <button onClick={() => act('start')}>开始审批</button>}
      {role === 'approver' && detail.application.status === '审批中' && <><label>审批意见<textarea value={note} onChange={e => setNote(e.target.value)} /></label>
        <button disabled={!note.trim()} onClick={() => act('approve')}>审批通过</button><button disabled={!note.trim()} onClick={() => act('reject')}>审批未通过</button></>}
      {records.map((r, i) => <p key={i}>{r.occurred_at} · {r.action} · {r.note} · {r.actor_id}</p>)}
    </>}
  </section>;
}
