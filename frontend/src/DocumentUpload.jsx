import React, { useState, useEffect } from 'react';

const types = {'M-C01':'授信申请表','M-C02':'主体登记资料','M-C03':'经营情况说明','M-E01':'设备采购计划','D-QUOTE':'设备报价单','D-UNSIGNED':'未签约说明'};
export default function DocumentUpload({ applicationId }) {
  const [category,setCategory]=useState('M-C01');
  const [file,setFile]=useState(null);
  const [items,setItems]=useState([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const path='/api/applications/'+encodeURIComponent(applicationId)+'/documents';
  async function refresh() { const response=await fetch(path); if(!response.ok) throw new Error('读取文件失败'); setItems(await response.json()); }
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[applicationId]);
  async function upload() {
    if(!file)return;
    setBusy(true);setError('');
    try {
      const response=await fetch(path+'?category='+category+'&filename='+encodeURIComponent(file.name),{method:'POST',body:file});
      const body=await response.json();
      if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'上传失败');
      await refresh();
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="review-item" aria-label="真实文件上传">
    <h3>上传教学材料原件</h3><p>PDF或DOCX，最大10MB；扫描件需另行OCR。字段按“字段名：内容”识别，未知版式需人工核验。</p>
    <select aria-label="上传材料类别" value={category} onChange={e=>setCategory(e.target.value)}>{Object.entries(types).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select>
    <input type="file" accept=".pdf,.docx" onChange={e=>setFile(e.target.files[0])}/>
    <button onClick={upload} disabled={busy||!file}>{busy?'上传中…':'上传并解析'}</button>
    {error&&<p role="alert">{error}</p>}
    {items.map(item=><article key={item.id}><a href={path+'/'+item.id}>{item.filename}</a> · 第{item.version}版 · {item.parsed.status==='parsed'?'正文已解析':'解析失败'}
      <details><summary>查看实际解析内容</summary>{item.parsed.sections.map((s,i)=><p key={i}>{s.location}：{s.text}</p>)}{item.parsed.error&&<p>{item.parsed.error}</p>}</details>
    </article>)}
  </section>;
}
