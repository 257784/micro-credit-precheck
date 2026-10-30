import React from 'react';
import { formatAmount, reportLabel } from './formatters.js';
import {
  applicationStatusLabels,
  reportStatusLabels,
  summarizeApplications,
} from './dashboardSummary.js';

function Metric({ label, count }) {
  return (
    <div className="dashboard-metric">
      <strong>{count}</strong>
      <span>{label}</span>
    </div>
  );
}

export default function RiskDashboard({ applications, error, loading, onRetry, onSelect }) {
  const summary = summarizeApplications(applications);

  return (
    <section className="panel risk-dashboard" aria-labelledby="dashboard-heading">
      <h2 id="dashboard-heading">风险与待办看板</h2>
      <p className="helper-text">
        根据申请状态和最新报告处理状态汇总教学样例；报告关注项需人工核验，不代表风险评级或授信决定。
      </p>
      {loading && <p role="status">正在读取看板…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button type="button" className="retry-button" onClick={onRetry}>重新加载看板</button>
        </div>
      )}
      {!loading && !error && applications.length === 0 && (
        <p className="notice">暂无申请，当前没有可汇总的预审状态。</p>
      )}
      {!loading && !error && applications.length > 0 && (
        <>
          <div className="dashboard-total">当前申请 <strong>{summary.total}</strong> 笔</div>
          <section className="dashboard-section" aria-labelledby="application-stats-heading">
            <h3 id="application-stats-heading">申请状态</h3>
            <div className="dashboard-metrics">
              {applicationStatusLabels.map((status) => (
                <Metric key={status} label={status} count={summary.applicationCounts[status]} />
              ))}
              {summary.applicationCounts.other > 0 && (
                <Metric label="其他申请状态" count={summary.applicationCounts.other} />
              )}
            </div>
          </section>
          <section className="dashboard-section" aria-labelledby="report-stats-heading">
            <h3 id="report-stats-heading">最新报告处理状态</h3>
            <div className="dashboard-metrics">
              {reportStatusLabels.map(({ key, label }) => (
                <Metric key={key} label={label} count={summary.reportCounts[key]} />
              ))}
              {summary.reportCounts.other > 0 && (
                <Metric label="其他报告状态" count={summary.reportCounts.other} />
              )}
            </div>
            <p className="helper-text">
              报告状态记录生成时的结果，不随人工复核改写；当前待办以申请状态为准。
              解析失败和暂无报告不能视为无风险。
            </p>
          </section>
          <section className="dashboard-section" aria-labelledby="dashboard-list-heading">
            <h3 id="dashboard-list-heading">申请概览</h3>
            <div className="dashboard-applications">
              {applications.map((application) => (
                <button
                  key={application.application_id}
                  type="button"
                  className="dashboard-application"
                  onClick={() => onSelect(application.application_id)}
                >
                  <span>
                    <strong>{application.enterprise_name}</strong>
                    <small>{application.application_id} · {application.product_type}</small>
                  </span>
                  <span className="dashboard-application-state">
                    <span>{application.status}</span>
                    <small>报告：{reportLabel(application.report_status)}</small>
                  </span>
                  <span className="dashboard-amount">{formatAmount(application.requested_amount)}</span>
                  <span className="dashboard-open">查看详情 →</span>
                </button>
              ))}
            </div>
          </section>
        </>
      )}
    </section>
  );
}
