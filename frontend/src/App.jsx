import React, { useCallback, useEffect, useState } from 'react';
import { getJson } from './api.js';
import ApplicationDetail from './ApplicationDetail.jsx';
import ApplicationList from './ApplicationList.jsx';
import './App.css';

function applicationIdFromUrl() {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get('application');
}

export default function App() {
  const [applications, setApplications] = useState([]);
  const [listError, setListError] = useState('');
  const [listLoading, setListLoading] = useState(true);
  const [listReloadKey, setListReloadKey] = useState(0);
  const [selectedId, setSelectedId] = useState(applicationIdFromUrl);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailReloadKey, setDetailReloadKey] = useState(0);

  const handleSelect = useCallback((applicationId) => {
    const url = new URL(window.location.href);
    if (applicationId) url.searchParams.set('application', applicationId);
    else url.searchParams.delete('application');
    if (url.href !== window.location.href) window.history.pushState(null, '', url.href);

    setSelectedId(applicationId);
    setDetail(null);
    setDetailError('');
    setDetailLoading(false);
  }, []);

  useEffect(() => {
    const handlePopState = () => handleSelect(applicationIdFromUrl());
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [handleSelect]);

  useEffect(() => {
    const controller = new AbortController();
    setListLoading(true);
    setListError('');

    getJson('/api/applications', '申请列表', controller.signal)
      .then((rows) => {
        setApplications(rows);
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setApplications([]);
          setListError(error.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setListLoading(false);
      });

    return () => controller.abort();
  }, [listReloadKey]);

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
  }, [selectedId, detailReloadKey]);

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">F2 · 虚构教学数据</p>
        <h1>授信申请与预审样例</h1>
        <p>从申请进入企业、材料和 AI 预审报告。当前数据只读，尚未接入人工复核提交。</p>
        {selectedId && (
          <button type="button" className="back-button" onClick={() => handleSelect(null)}>
            ← 返回申请列表
          </button>
        )}
      </header>

      <div className={selectedId ? 'detail-view' : 'list-view'}>
        <div hidden={Boolean(selectedId)}>
          <ApplicationList
            applications={applications}
            error={listError}
            loading={listLoading}
            onRetry={() => setListReloadKey((value) => value + 1)}
            onSelect={handleSelect}
            selectedId={selectedId}
          />
        </div>
        {selectedId && (
          <ApplicationDetail
            detail={detail}
            error={detailError}
            loading={detailLoading}
            onRetry={() => setDetailReloadKey((value) => value + 1)}
          />
        )}
      </div>
    </main>
  );
}
