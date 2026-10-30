import React from 'react';
import { formatTime, knowledgeLabel, reportLabel } from './formatters.js';
import RiskPrecheck from './RiskPrecheck.jsx';

const aspectStatusLabel = {
  needs_review: '待人工核验',
  insufficient_evidence: '证据不足',
  not_evaluated: '未形成判断',
};

function hasStructuredSummary(report) {
  return Boolean(
    report.material_completeness &&
    report.policy_match &&
    report.precheck_advice &&
    Array.isArray(report.risk_prompts),
  );
}

function ReportAspectCard({ title, aspect, reportId, materials, onOpenMaterials, showKnowledge = false }) {
  return (
    <article className="report-aspect">
      <h4>{title}</h4>
      <p className="aspect-status">{aspectStatusLabel[aspect.status]}</p>
      <p>{aspect.summary}</p>
      {aspect.material_ids.length > 0 && (
        <div className="aspect-references">
          <strong>相关材料</strong>
          {aspect.material_ids.map((materialId) => {
            const material = materials.find((entry) => entry.material_id === materialId);
            return (
              <button
                type="button"
                className="text-button"
                key={materialId}
                onClick={() => onOpenMaterials(materialId)}
              >
                {material ? material.file_name + ' · 第 ' + material.version_no + ' 版' : materialId} →
              </button>
            );
          })}
        </div>
      )}
      {aspect.item_ids.length > 0 && (
        <p>关联关注项：{aspect.item_ids.map((itemId, index) => (
          <React.Fragment key={itemId}>
            {index > 0 && '、'}<a href={'#' + reportId + '-' + itemId}>{itemId}</a>
          </React.Fragment>
        ))}</p>
      )}
      {aspect.knowledge_refs.length > 0 && (
        <div className="aspect-references">
          <strong>教学知识依据</strong>
          {aspect.knowledge_refs.map((reference) => (
            <span key={reference.knowledge_id + '-' + reference.version}>
              {knowledgeLabel(reference)}
            </span>
          ))}
        </div>
      )}
      {showKnowledge && aspect.knowledge_refs.length === 0 && (
        <p>教学知识依据：{aspect.status === 'not_evaluated' ? '未形成判断' : '无适用依据'}</p>
      )}
    </article>
  );
}

function Finding({ item, reportId, onOpenMaterials }) {
  const matchLabel = item.match_status === 'insufficient_evidence'
    ? '证据不足／待核验'
    : item.match_status === 'matched' ? '有对应描述／待人工核验' : '待人工核验';

  return (
    <article className="finding" id={reportId + '-' + item.item_id}>
      <h4>{item.field_name} · {matchLabel}</h4>
      <p>申请信息：{item.application_value || '未提供'}</p>
      <p>材料信息：{item.material_value || '暂无可核对数值'}</p>
      <p>核验原因：{item.reason}</p>
      <p>建议人工操作：{item.suggested_human_action}</p>
      <p>知识依据：{knowledgeLabel(item.knowledge_ref)}</p>
      <div className="evidence-list">
        <strong>材料证据</strong>
        {item.evidence.length === 0 && <p className="notice">暂无材料证据，需人工核实。</p>}
        {item.evidence.map((ref, index) => (
          <p key={ref.material_id + '-' + index}>
            {ref.file_name} · 第 {ref.page} 页 · “{ref.quote}”
            <br /><small>材料编号：{ref.material_id}</small>
            <br /><button type="button" className="text-button" onClick={() => onOpenMaterials(ref.material_id)}>
              查看这份材料及版本 →
            </button>
          </p>
        ))}
      </div>
    </article>
  );
}

export default function ReportPage({ detail, error, loading, onRetry, onOpenMaterials, onOpenReview }) {
  const reports = [...(detail?.reports ?? [])].sort((a, b) =>
    new Date(b.generated_at) - new Date(a.generated_at),
  );
  const latestReport = reports[0];
  const newerMaterials = latestReport && detail.materials.some((material) =>
    new Date(material.submitted_at) > new Date(latestReport.generated_at),
  );

  return (
    <section className="panel report-page" aria-labelledby="report-heading">
      <h2 id="report-heading">AI 预审报告</h2>
      {loading && <p role="status">正在读取报告…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button type="button" className="retry-button" onClick={onRetry}>重新加载报告</button>
        </div>
      )}
      {detail && (
        <>
          <p className="materials-context">{detail.enterprise.enterprise_name} · {detail.application.application_id}</p>
          <p className="helper-text">AI 预审仅整理待核验线索，不作授信审批结论。证据与正式材料须人工核对。</p>
          <RiskPrecheck key={detail.application.application_id} applicationId={detail.application.application_id} />
          <div className="page-actions">
            <button type="button" className="secondary-button" onClick={() => onOpenMaterials()}>查看本申请材料</button>
            <button type="button" className="retry-button" onClick={onOpenReview}>进入人工复核</button>
          </div>
          {newerMaterials && (
            <p className="notice">有材料提交时间晚于最新报告。请核对新版本是否已被人工复核；当前报告只引用其生成时的材料。</p>
          )}
          {reports.length === 0 && (
            <p className="notice">暂无 AI 预审报告，不能视为无风险；请人工核实材料与处理状态。</p>
          )}
          {reports.map((report) => (
            <section className="report-record" key={report.report_id}>
              <h3>{report.report_id}</h3>
              <dl className="facts">
                <dt>处理状态</dt><dd>{reportLabel(report.analysis_status)}</dd>
                <dt>生成时间</dt><dd>{formatTime(report.generated_at)}</dd>
                <dt>知识版本</dt><dd>{report.knowledge_version}</dd>
              </dl>
              {report.error_message && <p className="notice" role="alert">{report.error_message}</p>}
              {hasStructuredSummary(report) ? (
                <div className="report-aspects" aria-label="结构化预审摘要">
                  <ReportAspectCard
                    title="材料完整性核对"
                    aspect={report.material_completeness}
                    reportId={report.report_id}
                    materials={detail.materials}
                    onOpenMaterials={onOpenMaterials}
                  />
                  <div className="report-prompt-group">
                    {report.risk_prompts.length === 0 ? (
                      <article className="report-aspect">
                        <h4>风险提示（待核验）</h4>
                        <p className="notice">本次未生成风险提示，不能据此判断为无风险。</p>
                      </article>
                    ) : report.risk_prompts.map((prompt, index) => (
                      <ReportAspectCard
                        key={index}
                        title={'风险提示（待核验）' + (report.risk_prompts.length > 1 ? ' ' + (index + 1) : '')}
                        aspect={prompt}
                        reportId={report.report_id}
                        materials={detail.materials}
                        onOpenMaterials={onOpenMaterials}
                      />
                    ))}
                  </div>
                  <ReportAspectCard
                    title="政策／教学规则匹配"
                    aspect={report.policy_match}
                    reportId={report.report_id}
                    materials={detail.materials}
                    onOpenMaterials={onOpenMaterials}
                    showKnowledge
                  />
                  <ReportAspectCard
                    title="预审建议"
                    aspect={report.precheck_advice}
                    reportId={report.report_id}
                    materials={detail.materials}
                    onOpenMaterials={onOpenMaterials}
                  />
                </div>
              ) : (
                <p className="notice">当前报告缺少结构化摘要，请重启后端并刷新页面。</p>
              )}
              <h4>关注项明细</h4>
              {report.items.length === 0 && report.analysis_status !== 'failed' && (
                <p className="notice">报告暂无关注项，仍需人工核实，不代表无风险。</p>
              )}
              {report.items.map((item) => (
                <Finding key={item.item_id} item={item} reportId={report.report_id} onOpenMaterials={onOpenMaterials} />
              ))}
            </section>
          ))}
        </>
      )}
    </section>
  );
}
