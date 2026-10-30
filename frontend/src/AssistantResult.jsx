import React from 'react';

export default function AssistantResult({ result }) {
  return <article className="record" aria-label="助手结构化结果">
    <p><strong>助手：</strong>{result.summary}</p>
    <p>处理状态：{result.status}；申请：{result.application_id || '未指定'}；运行编号：{result.run_id}</p>
    <h4>申请事实</h4>
    {result.facts.length ? result.facts.map((fact, i) => <p key={i}>{fact.label}：{fact.value}（{fact.source_tool}）</p>) : <p>本轮未查询到申请事实。</p>}
    <h4>材料问题</h4>
    {result.material_issues.length ? result.material_issues.map((item, i) => <p key={i}>工具内容待人工核验 · {item.code || item.category}：{item.description} {item.action || ''} {item.material_id && `（材料 ${item.material_id} 版本 ${item.version}）`}</p>) : <p>本轮没有列出材料问题；未检查不代表完整。</p>}
    <h4>风险线索</h4>
    {result.risk_items.length ? result.risk_items.map((item, i) => <div key={i}><p>工具内容待人工核验 · {item.description}</p>
      {item.evidence.map((e, j) => <p key={j}>不可信材料原文 · {e.material_id} 版本 {e.version} · {e.location}：“{e.quote}”</p>)}
      {item.policy_ref && <p>规则依据：{item.policy_ref.join(' · ')}</p>}<p>{item.suggested_action}</p></div>) : <p>本轮没有列出风险线索；不代表无风险。</p>}
    <h4>政策检索来源</h4>
    {result.policy_sources.length ? result.policy_sources.map((item, i) => <p key={i}>{item.document_id} · {item.version} · {item.clause}（{item.source_path}:{item.source_line}）</p>) : <p>本轮没有可展示的政策检索来源。</p>}
    <h4>待补充信息</h4>{result.missing_info.length ? result.missing_info.map((item, i) => <p key={i}>{item}</p>) : <p>本轮没有列出其他缺口。</p>}
    <p>需要人工复核：{result.need_human_review ? '是' : '否'}</p>
    {result.limitations.map((item, i) => <p key={i}>{item}</p>)}
    <details><summary>查看结构化结果</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(result, null, 2)}</pre></details>
  </article>;
}
