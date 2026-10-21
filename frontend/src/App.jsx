import { useEffect, useState } from 'react';
import './App.css';

const money = new Intl.NumberFormat('zh-CN');

function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—';
}

function reportLabel(status) {
  if (status === 'failed') return '解析失败';
  if (status === 'needs_human_review') return '待人工核验';
  return status || '暂无报告';
}

export default function App() {
  const [applications, setApplications] = useState([]);
  const [listError, setListError] = useState('');
  const [listLoading, setListLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/applications', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('申请列表读取失败（' + response.status + '）');
        return response.json();
      })
      .then((rows) => {
        setApplications(rows);
        if (rows.length > 0) setSelectedId(rows[0].application_id);
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setListError(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setListLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedId) return undefined;
    const controller = new AbortController();
    setDetail(null);
    setDetailError('');
    setDetailLoading(true);
    fetch('/api/applications/' + encodeURIComponent(selectedId), { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('申请详情读取失败（' + response.status + '）');
        return response.json();
      })
      .then(setDetail)
      .catch((error) => {
        if (error.name !== 'AbortError') setDetailError(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setDetailLoading(false);
      });
    return () => controller.abort();
  }, [selectedId]);

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">F2 · 虚构教学数据</p>
        <h1>授信申请与预审样例</h1>
        <p>从申请进入企业、材料和 AI 预审报告。当前数据只读，尚未接入人工复核提交。</p>
      </header>

      <div className="columns">
        <section className="panel" aria-labelledby="application-heading">
          <h2 id="application-heading">授信申请</h2>
          {listLoading && <p role="status">正在读取申请…</p>}
          {listError && <p role="alert">{listError}。请检查后端是否启动。</p>}
          {!listLoading && !listError && applications.length === 0 && <p>暂无申请。</p>}
          <div className="application-list">
            {applications.map((application) => (
              <button
                className={'application-card ' + (selectedId === application.application_id ? 'selected' : '')}
                key={application.application_id}
                onClick={() => setSelectedId(application.application_id)}
                aria-pressed={selectedId === application.application_id}
                type="button"
              >
                <span className="card-top"><strong>{application.enterprise_name}</strong><span>{application.status}</span></span>
                <span>{application.application_id} · {application.product_type}</span>
                <span>申请金额：¥{money.format(application.requested_amount)}</span>
                <span>报告：{reportLabel(application.report_status)}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="panel detail" aria-labelledby="detail-heading">
          <h2 id="detail-heading">申请详情</h2>
          {!selectedId && !listLoading && <p>选择一笔申请查看详情。</p>}
          {detailLoading && <p role="status">正在读取详情…</p>}
          {detailError && <p role="alert">{detailError}</p>}
          {detail && (
            <>
              <section>
                <h3>企业客户与申请</h3>
                <dl className="facts">
                  <dt>企业名称</dt><dd>{detail.enterprise.enterprise_name}</dd>
                  <dt>行业 / 地区</dt><dd>{detail.enterprise.industry} / {detail.enterprise.registered_region}</dd>
                  <dt>申请编号</dt><dd>{detail.application.application_id}</dd>
                  <dt>申请金额</dt><dd>¥{money.format(detail.application.requested_amount)}</dd>
                  <dt>客户经理</dt><dd>{detail.application.account_manager_name}</dd>
                  <dt>提交时间</dt><dd>{formatTime(detail.application.submitted_at)}</dd>
                </dl>
              </section>

              <section>
                <h3>申请材料</h3>
                {detail.materials.length === 0 && <p>暂无材料，需人工核实。</p>}
                {detail.materials.map((material) => (
                  <div className="record" key={material.material_id}>
                    <strong>{material.file_name}</strong>
                    <p>{material.material_type} · 第 {material.version_no} 版 · {material.check_status}</p>
                    <small>{material.preview_url ? '已有预览地址' : '暂无样例文件预览'}</small>
                  </div>
                ))}
              </section>

              <section>
                <h3>AI 预审报告</h3>
                {detail.reports.length === 0 && <p>暂无报告，不能视为无风险；请人工核实处理状态。</p>}
                {detail.reports.map((report) => (
                  <div className="record" key={report.report_id}>
                    <p><strong>{report.report_id}</strong> · {reportLabel(report.analysis_status)} · {formatTime(report.generated_at)}</p>
                    {report.error_message && <p className="notice" role="alert">{report.error_message}</p>}
                    {report.items.map((item) => (
                      <div className="finding" key={item.item_id}>
                        <strong>{item.field_name} · {item.match_status === 'insufficient_evidence' ? '证据不足' : '待核验'}</strong>
                        <p>{item.reason}</p>
                        <p>建议：{item.suggested_human_action}</p>
                        {item.evidence.map((evidence) => (
                          <p key={item.item_id + '-' + evidence.material_id}>
                            证据：{evidence.file_name} 第 {evidence.page} 页 · “{evidence.quote}”
                          </p>
                        ))}
                        <p>知识依据：{item.knowledge_ref
                          ? item.knowledge_ref.knowledge_id + ' / ' + item.knowledge_ref.version + ' · ' + item.knowledge_ref.requirement
                          : '无适用依据'}</p>
                      </div>
                    ))}
                  </div>
                ))}
              </section>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
