import { formatAmount, reportLabel } from './formatters.js';

export default function ApplicationList({
  applications,
  error,
  loading,
  onSelect,
  selectedId,
}) {
  return (
    <section className="panel" aria-labelledby="application-heading">
      <h2 id="application-heading">授信申请</h2>
      {loading && <p role="status">正在读取申请…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && applications.length === 0 && <p>暂无申请。</p>}

      <div className="application-list">
        {applications.map((application) => (
          <button
            key={application.application_id}
            type="button"
            className={
              'application-card ' +
              (selectedId === application.application_id ? 'selected' : '')
            }
            aria-pressed={selectedId === application.application_id}
            onClick={() => onSelect(application.application_id)}
          >
            <span className="card-top">
              <strong>{application.enterprise_name}</strong>
              <span>{application.status}</span>
            </span>
            <span>{application.application_id} · {application.product_type}</span>
            <span>申请金额：{formatAmount(application.requested_amount)}</span>
            <span>报告：{reportLabel(application.report_status)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
