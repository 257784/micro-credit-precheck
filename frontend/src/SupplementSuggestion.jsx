import React, { useState } from 'react';
import { postJson } from './api.js';

export default function SupplementSuggestion({ applicationId, onSaved }) {
  const [note, setNote] = useState('');
  const [message, setMessage] = useState('');
  async function submit() {
    try {
      await postJson('/api/applications/' + encodeURIComponent(applicationId) + '/supplement-suggestion', '补件建议', 'customer_manager', { note });
      setNote(''); setMessage('补件建议已记录，申请状态未改变。'); onSaved();
    } catch (error) { setMessage(error.message); }
  }
  return <section className="panel"><h3>补件建议</h3><p>建议不会直接退回申请，正式补件由风控处理。</p>
    <textarea value={note} onChange={event => setNote(event.target.value)} maxLength={2000} />
    <button disabled={!note.trim()} onClick={submit}>记录建议</button>{message && <p role="status">{message}</p>}
  </section>;
}
