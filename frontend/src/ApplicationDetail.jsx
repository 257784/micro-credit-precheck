import React from 'react';
import {
  formatAmount,
  formatTime,
  knowledgeLabel,
  reportLabel,
} from './formatters.js';

function ReportFinding({ item }) {
  const matchLabel =
    item.match_status === 'insufficient_evidence' ? '证据不足' : '待核验';

  return (
    <div className="finding">
      <strong>{item.field_name} · {matchLabel}</strong>
      <p>{item.reason}</p>
      <p>建议：{item.suggested_human_action}</p>
      {item.evidence.length === 0 && <p>暂无材料证据，需人工核验。</p>}
      {item.evidence.map((evidence, index) => (
        <p key={item.item_id + '-' + evidence.material_id + '-' + index}>
          证据：{evidence.file_name} 第 {evidence.page} 页 · “{evidence.quote}”
        </p>
      ))}
      <p>知识依据：{knowledgeLabel(item.knowledge_ref)}</p>
    </div>
  );
}

function ReportSection({ reports }) {
  return (
    <section id="detail-report">
      <h3>AI 预审报告</h3>
      {reports.length === 0 && (
        <p>暂无报告，不能视为无风险；请人工核实处理状态。</p>
      )}
      {reports.map((report) => (
        <div className="record" key={report.report_id}>
          <p>
            <strong>{report.report_id}</strong> · {reportLabel(report.analysis_status)} ·{' '}
            {formatTime(report.generated_at)}
          </p>
          {report.error_message && (
            <p className="notice" role="alert">{report.error_message}</p>
          )}
          {report.items.map((item) => (
            <ReportFinding key={item.item_id} item={item} />
          ))}
        </div>
      ))}
    </section>
  );
}

export default function ApplicationDetail({ detail, error, loading, onRetry }) {
  const statusHistory = detail?.status_history ?? [];

  return (
    <section className="panel detail" aria-labelledby="detail-heading">
      <h2 id="detail-heading">申请详情</h2>
      {loading && <p role="status">正在读取详情…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button type="button" className="retry-button" onClick={onRetry}>
            重新加载详情
          </button>
        </div>
      )}

      {detail && (
        <>
          <div className="detail-summary">
            <div>
              <strong>{detail.enterprise.enterprise_name}</strong>
              <p>{detail.application.application_id}</p>
            </div>
            <span className="status-badge">{detail.application.status}</span>
          </div>

          <nav className="detail-nav" aria-label="申请详情目录">
            <a href="#detail-overview">申请概况</a>
            <a href="#detail-progress">进度</a>
            <a href="#detail-materials">申请材料</a>
            <a href="#detail-report">AI 预审报告</a>
          </nav>

          <section id="detail-overview">
            <h3>企业客户与申请</h3>
            <dl className="facts">
              <dt>企业名称</dt>
              <dd>{detail.enterprise.enterprise_name}</dd>
              <dt>行业 / 地区</dt>
              <dd>{detail.enterprise.industry} / {detail.enterprise.registered_region}</dd>
              <dt>申请编号</dt>
              <dd>{detail.application.application_id}</dd>
              <dt>产品类型</dt>
              <dd>{detail.application.product_type}</dd>
              <dt>申请金额</dt>
              <dd>{formatAmount(detail.application.requested_amount)}</dd>
              <dt>当前状态</dt>
              <dd>{detail.application.status}</dd>
              <dt>客户经理</dt>
              <dd>{detail.application.account_manager_name}</dd>
              <dt>提交时间</dt>
              <dd>{formatTime(detail.application.submitted_at)}</dd>
            </dl>
          </section>

          <section id="detail-progress">
            <h3>申请进度</h3>
            {statusHistory.length === 0 && <p>暂无进度记录，请人工核实当前状态。</p>}
            {statusHistory.length > 0 && (
              <ol className="timeline">
                {statusHistory.map((event) => (
                  <li key={event.event_id}>
                    <strong>{event.event_label}</strong>
                    <time dateTime={event.occurred_at}>{formatTime(event.occurred_at)}</time>
                  </li>
                ))}
              </ol>
            )}
            <p className="helper-text">进度时间为虚构教学样例，不代表正式审计记录。</p>
          </section>

          <section id="detail-materials">
            <h3>申请材料</h3>
            {detail.materials.length === 0 && <p>暂无材料，需人工核实。</p>}
            {detail.materials.map((material) => (
              <div className="record" key={material.material_id}>
                <strong>{material.file_name}</strong>
                <p>
                  {material.material_type} · 第 {material.version_no} 版 · {material.check_status}
                </p>
                <small>
                  提交于 {formatTime(material.submitted_at)} ·{' '}
                  {material.preview_url ? '已有预览地址' : '暂无样例文件预览'}
                </small>
                {material.check_status === '解析失败' && (
                  <p className="notice">材料无法解析，请人工核对或联系客户经理补交可读取版本。</p>
                )}
              </div>
            ))}
          </section>

          <ReportSection reports={detail.reports} />
        </>
      )}
    </section>
  );
}
