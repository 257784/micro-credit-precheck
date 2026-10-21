import React, { useState } from 'react';
import { filterApplications } from './applicationFilters.js';
import { formatAmount, formatTime, reportLabel } from './formatters.js';

export default function ApplicationList({
  applications,
  error,
  loading,
  onRetry,
  onSelect,
  selectedId,
}) {
  const [searchText, setSearchText] = useState('');
  const [status, setStatus] = useState('');
  const statuses = [...new Set(applications.map((application) => application.status))];
  const visibleApplications = filterApplications(applications, searchText, status);

  function changeSearch(event) {
    setSearchText(event.target.value);
    onSelect(null);
  }

  function changeStatus(event) {
    setStatus(event.target.value);
    onSelect(null);
  }

  return (
    <section className="panel" aria-labelledby="application-heading">
      <h2 id="application-heading">授信申请</h2>
      {loading && <p role="status">正在读取申请…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button type="button" className="retry-button" onClick={onRetry}>
            重新加载
          </button>
        </div>
      )}
      {!loading && !error && applications.length === 0 && <p>暂无申请。</p>}

      {!loading && !error && applications.length > 0 && (
        <div className="filters">
          <label htmlFor="application-search">申请编号或企业名称</label>
          <input
            id="application-search"
            type="search"
            value={searchText}
            onChange={changeSearch}
            placeholder="输入编号或企业名称"
          />
          <label htmlFor="application-status">状态</label>
          <select id="application-status" value={status} onChange={changeStatus}>
            <option value="">全部状态</option>
            {statuses.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
      )}

      {!loading && !error && applications.length > 0 && visibleApplications.length === 0 && (
        <p role="status">没有符合条件的申请。</p>
      )}

      {!loading && !error && (
        <div className="application-list">
          {visibleApplications.map((application) => (
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
              <span>客户经理：{application.account_manager_name}</span>
              <span>提交时间：{formatTime(application.submitted_at)}</span>
              <span>报告：{reportLabel(application.report_status)}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
