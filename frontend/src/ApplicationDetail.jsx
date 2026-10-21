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
    <section>
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

export default function ApplicationDetail({ detail, error, loading, showPrompt }) {
  return (
    <section className="panel detail" aria-labelledby="detail-heading">
      <h2 id="detail-heading">申请详情</h2>
      {showPrompt && <p>选择一笔申请查看详情。</p>}
      {loading && <p role="status">正在读取详情…</p>}
      {error && <p role="alert">{error}</p>}

      {detail && (
        <>
          <section>
            <h3>企业客户与申请</h3>
            <dl className="facts">
              <dt>企业名称</dt>
              <dd>{detail.enterprise.enterprise_name}</dd>
              <dt>行业 / 地区</dt>
              <dd>{detail.enterprise.industry} / {detail.enterprise.registered_region}</dd>
              <dt>申请编号</dt>
              <dd>{detail.application.application_id}</dd>
              <dt>申请金额</dt>
              <dd>{formatAmount(detail.application.requested_amount)}</dd>
              <dt>客户经理</dt>
              <dd>{detail.application.account_manager_name}</dd>
              <dt>提交时间</dt>
              <dd>{formatTime(detail.application.submitted_at)}</dd>
            </dl>
          </section>

          <section>
            <h3>申请材料</h3>
            {detail.materials.length === 0 && <p>暂无材料，需人工核实。</p>}
            {detail.materials.map((material) => (
              <div className="record" key={material.material_id}>
                <strong>{material.file_name}</strong>
                <p>
                  {material.material_type} · 第 {material.version_no} 版 ·{' '}
                  {material.check_status}
                </p>
                <small>
                  {material.preview_url ? '已有预览地址' : '暂无样例文件预览'}
                </small>
              </div>
            ))}
          </section>

          <ReportSection reports={detail.reports} />
        </>
      )}
    </section>
  );
}
