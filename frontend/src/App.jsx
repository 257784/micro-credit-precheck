import React, { useCallback, useEffect, useState } from 'react';
import { getJson, postJson } from './api.js';
import ApplicationDetail from './ApplicationDetail.jsx';
import ApplicationList from './ApplicationList.jsx';
import MaterialList from './MaterialList.jsx';
import ReportPage from './ReportPage.jsx';
import ReviewPage from './ReviewPage.jsx';
import RiskDashboard from './RiskDashboard.jsx';
import PolicyQa from './PolicyQa.jsx';
import CreditAssistant from './CreditAssistant.jsx';
import EnterpriseApplication from './EnterpriseApplication.jsx';
import './App.css';

function applicationIdFromUrl() {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get('application');
}

function demoRoleFromSession() {
  if (typeof window === 'undefined') return 'risk_reviewer';
  const saved = window.sessionStorage.getItem('demo-role');
  return ['enterprise', 'risk_reviewer', 'customer_manager'].includes(saved) ? saved : 'risk_reviewer';
}

function viewFromUrl() {
  if (typeof window === 'undefined') return 'detail';
  const params = new URLSearchParams(window.location.search);
  const requested = params.get('view');
  return params.get('application') && ['materials', 'report', 'review', 'assistant', 'approval'].includes(requested)
    ? requested
    : 'detail';
}

function materialIdFromUrl() {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get('material');
}

function homeViewFromUrl() {
  if (typeof window === 'undefined') return 'applications';
  const params = new URLSearchParams(window.location.search);
  if (!params.get('application') && params.get('view') === 'policy') return 'policy';
  if (!params.get('application') && params.get('view') === 'assistant') return 'assistant';
  return params.get('from') === 'dashboard' ||
    (!params.get('application') && params.get('view') === 'dashboard')
    ? 'dashboard' : 'applications';
}

export default function App() {
  const [applications, setApplications] = useState([]);
  const [listError, setListError] = useState('');
  const [listLoading, setListLoading] = useState(true);
  const [listReloadKey, setListReloadKey] = useState(0);
  const [selectedId, setSelectedId] = useState(applicationIdFromUrl);
  const [view, setView] = useState(viewFromUrl);
  const [homeView, setHomeView] = useState(homeViewFromUrl);
  const [materialId, setMaterialId] = useState(materialIdFromUrl);
  const [role, setRole] = useState(demoRoleFromSession);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailReloadKey, setDetailReloadKey] = useState(0);

  const handleSelect = useCallback((applicationId) => {
    const url = new URL(window.location.href);
    if (applicationId) {
      url.searchParams.set('application', applicationId);
      if (homeView === 'dashboard') url.searchParams.set('from', 'dashboard');
      else url.searchParams.delete('from');
    } else {
      url.searchParams.delete('application');
      url.searchParams.delete('from');
    }
    if (!applicationId && homeView === 'dashboard') url.searchParams.set('view', 'dashboard');
    else url.searchParams.delete('view');
    url.searchParams.delete('material');
    if (url.href !== window.location.href) window.history.pushState(null, '', url.href);

    setSelectedId(applicationId);
    setView('detail');
    setMaterialId(null);
    setDetail(null);
    setDetailError('');
    setDetailLoading(false);
  }, [homeView]);

  const showHome = (nextHomeView) => {
    const url = new URL(window.location.href);
    url.searchParams.delete('application');
    url.searchParams.delete('material');
    url.searchParams.delete('from');
    if (['dashboard', 'policy', 'assistant'].includes(nextHomeView)) url.searchParams.set('view', nextHomeView);
    else url.searchParams.delete('view');
    if (url.href !== window.location.href) window.history.pushState(null, '', url.href);
    setSelectedId(null);
    setView('detail');
    setHomeView(nextHomeView);
    setMaterialId(null);
    setDetail(null);
    setDetailError('');
  };

  const navigateView = (nextView, requestedMaterialId = null) => {
    const url = new URL(window.location.href);
    if (nextView === 'detail') url.searchParams.delete('view');
    else url.searchParams.set('view', nextView);
    if (nextView === 'materials' && requestedMaterialId) {
      url.searchParams.set('material', requestedMaterialId);
    } else {
      url.searchParams.delete('material');
    }
    if (url.href !== window.location.href) window.history.pushState(null, '', url.href);
    setView(nextView);
    setMaterialId(nextView === 'materials' ? requestedMaterialId : null);
  };

  useEffect(() => {
    const handlePopState = () => {
      setSelectedId(applicationIdFromUrl());
      setView(viewFromUrl());
      setHomeView(homeViewFromUrl());
      setMaterialId(materialIdFromUrl());
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    if (role === 'enterprise') return undefined;
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
  }, [listReloadKey, role]);

  useEffect(() => {
    if (!selectedId || role === 'enterprise') return undefined;

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
  }, [selectedId, detailReloadKey, role]);

  const runReviewAction = async (action, payload) => {
    const updated = await postJson(
      '/api/applications/' + encodeURIComponent(selectedId) + '/review/' + action,
      action === 'start' ? '开始复核' : '提交复核',
      role,
      payload,
    );
    setDetail(updated);
    setListReloadKey((value) => value + 1);
    return updated;
  };

  const denied = role === 'enterprise' ? false :
    (view === 'approval' && role !== 'customer_manager') ||
    (view === 'assistant' && role !== 'customer_manager') ||
    (!selectedId && ['assistant', 'policy'].includes(homeView) && role !== 'customer_manager') ||
    (!selectedId && homeView === 'dashboard');
  const changeRole = (nextRole) => {
    window.sessionStorage.setItem('demo-role', nextRole);
    setRole(nextRole);
    showHome('applications');
  };

  return (
    <div className="prototype-shell">
      <aside className="prototype-sidebar">
        <div className="prototype-brand"><b>信</b><span><strong>小微授信预审</strong><small>SMART CREDIT · 教学原型</small></span></div>
        <p className="prototype-label">业务工作区</p>
        <nav className="prototype-nav" aria-label="业务导航">
          {role === 'enterprise' ? <>
            <button className={homeView !== 'policy' ? 'active' : ''} type="button" onClick={() => showHome('applications')}>＋　企业申请</button>
            <button className={homeView === 'policy' ? 'active' : ''} type="button" onClick={() => showHome('policy')}>⌕　政策问答</button>
          </> : <>
            <button className={!selectedId && homeView === 'applications' ? 'active' : ''} onClick={() => showHome('applications')}>▦　授信工作台</button>
            <button disabled={!selectedId} className={selectedId && view === 'detail' ? 'active' : ''} onClick={() => navigateView('detail')}>▤　申请详情</button>
            <button disabled={!selectedId} className={selectedId && ['report', 'review'].includes(view) ? 'active' : ''} onClick={() => navigateView('report')}>◇　AI预审与复核</button>
            {role === 'customer_manager' && <button disabled={!selectedId} className={selectedId && view === 'approval' ? 'active' : ''} onClick={() => navigateView('approval')}>✓　审批处理</button>}
            {role === 'customer_manager' && <><button onClick={() => showHome('policy')}>⌕　政策问答</button><button onClick={() => showHome('assistant')}>✦　授信助手</button></>}
          </>}
        </nav>
        <div className="prototype-sidefoot">虚构数据 · 教学演示<br />角色切换不构成身份认证</div>
      </aside>
      <main className="page">
      <header className="page-header">
        <div><p className="eyebrow">F系列 PBL / 业务工作区</p><h1>小微企业授信智能预审</h1></div>
        <label className="role-switch">
          演示身份
          <select value={role} onChange={(event) => changeRole(event.target.value)}>
            <option value="enterprise">企业客户</option>
            <option value="risk_reviewer">风控专员</option>
            <option value="customer_manager">客户经理</option>
          </select>
        </label>
        {selectedId && role !== 'enterprise' && (
          <button
            type="button"
            className="back-button"
            onClick={view === 'detail' ? () => showHome(homeView) : () => navigateView('detail')}
          >
            {view === 'detail'
              ? '← 返回' + (homeView === 'dashboard' ? '风险看板' : '申请列表')
              : '← 返回申请详情'}
          </button>
        )}
      </header>

      {role === 'enterprise' ? (homeView === 'policy' && !selectedId ? <PolicyQa sessionKey="enterprise-policy-conversation" /> : <EnterpriseApplication onSubmitted={() => setListReloadKey((value) => value + 1)} />) : denied ?
        <section className="panel permission" role="alert"><h2>当前演示角色无法访问此页面</h2><p>请返回授信工作台或切换合适的演示角色。</p><button onClick={() => showHome('applications')}>返回工作台</button></section> :
      <div className={selectedId ? 'detail-view' : homeView === 'dashboard' ? 'dashboard-view' : 'list-view'}>
        <div hidden={Boolean(selectedId) || homeView !== 'applications'}>
          <ApplicationList
            applications={applications}
            error={listError}
            loading={listLoading}
            onRetry={() => setListReloadKey((value) => value + 1)}
            onSelect={handleSelect}
            selectedId={selectedId}
          />
        </div>
        {!selectedId && homeView === 'dashboard' && (
          <RiskDashboard
            applications={applications}
            error={listError}
            loading={listLoading}
            onRetry={() => setListReloadKey((value) => value + 1)}
            onSelect={handleSelect}
          />
        )}
        {!selectedId && homeView === 'policy' && <PolicyQa />}
        {!selectedId && homeView === 'assistant' && <CreditAssistant />}
        {selectedId && view === 'detail' && (
          <>{role === 'customer_manager' && <button type="button" onClick={() => navigateView('assistant')}>使用助手分析本申请</button>}<ApplicationDetail
            detail={detail}
            error={detailError}
            loading={detailLoading}
            onRetry={() => setDetailReloadKey((value) => value + 1)}
            onOpenMaterials={() => navigateView('materials')}
            onOpenReport={() => navigateView('report')}
            onOpenReview={() => navigateView('review')}
          /></>
        )}
        {selectedId && view === 'assistant' && <CreditAssistant key={selectedId} applicationId={selectedId} />}
        {selectedId && view === 'materials' && (
          <MaterialList
            key={selectedId + '-' + materialId}
            detail={detail}
            error={detailError}
            loading={detailLoading}
            onRetry={() => setDetailReloadKey((value) => value + 1)}
            onOpenReport={() => navigateView('report')}
            requestedMaterialId={materialId}
          />
        )}
        {selectedId && view === 'report' && (
          <ReportPage
            detail={detail}
            error={detailError}
            loading={detailLoading}
            onRetry={() => setDetailReloadKey((value) => value + 1)}
            onOpenMaterials={(requestedId) => navigateView('materials', requestedId)}
            onOpenReview={() => navigateView('review')}
          />
        )}
        {selectedId && view === 'review' && (
          <ReviewPage
            key={selectedId}
            detail={detail}
            error={detailError}
            loading={detailLoading}
            role={role}
            onRetry={() => setDetailReloadKey((value) => value + 1)}
            onOpenReport={() => navigateView('report')}
            onStart={() => runReviewAction('start')}
            onSubmit={(payload) => runReviewAction('submit', payload)}
          />
        )}
        {selectedId && view === 'approval' && <section className="panel"><p className="eyebrow">05 · APPROVAL</p><h2>审批处理与结果</h2>{detailLoading && <p>正在读取申请…</p>}{detailError && <p role="alert">{detailError}</p>}{detail && <><p>{detail.enterprise.enterprise_name} · {detail.application.application_id}</p><p>当前状态：<strong>{detail.application.status}</strong></p><p>客户经理可跟踪审批进度；正式审批及审批结果录入尚未实现，不能在此页面通过审批。</p></>}</section>}
      </div>}
    </main>
    </div>
  );
}
