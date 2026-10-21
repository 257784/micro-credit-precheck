import React, { useCallback, useEffect, useState } from 'react';
import { getJson } from './api.js';
import ApplicationDetail from './ApplicationDetail.jsx';
import ApplicationList from './ApplicationList.jsx';
import './App.css';

export default function App() {
  const [applications, setApplications] = useState([]);
  const [listError, setListError] = useState('');
  const [listLoading, setListLoading] = useState(true);
  const [listReloadKey, setListReloadKey] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);

  const handleSelect = useCallback((applicationId) => {
    setSelectedId(applicationId);
    setDetail(null);
    setDetailError('');
    setDetailLoading(false);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setListLoading(true);
    setListError('');

    getJson('/api/applications', '申请列表', controller.signal)
      .then((rows) => {
        setApplications(rows);
        handleSelect(rows[0]?.application_id ?? null);
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setApplications([]);
          handleSelect(null);
          setListError(error.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setListLoading(false);
      });

    return () => controller.abort();
  }, [handleSelect, listReloadKey]);

  useEffect(() => {
    if (!selectedId) return undefined;

    // 切换申请时取消旧请求，避免较慢的响应覆盖当前详情。
    const controller = new AbortController();
    setDetail(null);
    setDetailError('');
    setDetailLoading(true);

    getJson(
      '/api/applications/' + encodeURIComponent(selectedId),
      '申请详情',
      controller.signal,
    )
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
        <ApplicationList
          applications={applications}
          error={listError}
          loading={listLoading}
          onRetry={() => setListReloadKey((value) => value + 1)}
          onSelect={handleSelect}
          selectedId={selectedId}
        />
        <ApplicationDetail
          detail={detail}
          error={detailError}
          loading={detailLoading}
          selectedId={selectedId}
          showPrompt={!listLoading && !selectedId}
        />
      </div>
    </main>
  );
}
