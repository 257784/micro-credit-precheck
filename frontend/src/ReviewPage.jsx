import React, { useState } from 'react';
import { formatTime } from './formatters.js';

const resultLabel = {
  complete: '完成复核 → 待审批',
  request_supplement: '要求补件 → 待企业补充材料',
};

export default function ReviewPage({
  detail, error, loading, role, onRetry, onOpenReport, onStart, onSubmit,
}) {
  const [decisions, setDecisions] = useState({});
  const [reviewNote, setReviewNote] = useState('');
  const [overallAdoption, setOverallAdoption] = useState('');
  const [actionError, setActionError] = useState('');
  const [pending, setPending] = useState(false);
  const isRisk = role === 'risk_reviewer';
  const latestReport = [...(detail?.reports ?? [])].sort((a, b) =>
    new Date(b.generated_at) - new Date(a.generated_at),
  )[0];
  const items = latestReport?.analysis_status === 'failed' ? [] : (latestReport?.items ?? []);
  const newerMaterials = latestReport && detail.materials.some((material) =>
    new Date(material.submitted_at) > new Date(latestReport.generated_at),
  );

  async function runAction(action) {
    setActionError('');
    setPending(true);
    try {
      await action();
    } catch (requestError) {
      setActionError(requestError.message);
    } finally {
      setPending(false);
    }
  }

  function submit(result) {
    if (result === 'complete' && !overallAdoption) {
      setActionError('请先选择对 AI 预审报告的总体处理方式。');
      return;
    }
    if (!reviewNote.trim()) {
      setActionError('请填写人工复核意见或补件原因。');
      return;
    }
    const itemReviews = items.map((item) => ({
      item_id: item.item_id,
      decision: decisions[item.item_id]?.decision,
      correction_note: decisions[item.item_id]?.correctionNote || null,
    }));
    if (itemReviews.some((item) => !item.decision ||
      (['partial', 'rejected'].includes(item.decision) && !item.correction_note?.trim()))) {
      setActionError('请逐项选择采纳方式，部分采纳或不采纳时填写说明。');
      return;
    }
    runAction(() => onSubmit({
      review_result: result,
      overall_adoption: overallAdoption || null,
      review_note: reviewNote.trim(),
      item_reviews: itemReviews,
      report_id: latestReport?.report_id || null,
    }));
  }

  return (
    <section className="panel review-page" aria-labelledby="review-heading">
      <h2 id="review-heading">人工风控复核</h2>
      {loading && <p role="status">正在读取复核状态…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button type="button" className="retry-button" onClick={onRetry}>重新加载复核状态</button>
        </div>
      )}
      {detail && (
        <>
          <p className="materials-context">{detail.enterprise.enterprise_name} · {detail.application.application_id}</p>
          <p>当前状态：<strong>{detail.application.status}</strong></p>
          <p className="helper-text">本页为教学演示。风控复核是人工核验，不是正式授信审批。</p>
          <button type="button" className="text-button" onClick={onOpenReport}>查看本申请 AI 预审报告 →</button>
          {newerMaterials && (
            <p className="notice">有材料晚于最新报告提交。请核对补交版本，并在复核意见中说明处理依据。</p>
          )}

          {!isRisk && (
            <p className="notice">当前是客户经理只读身份，可以查看记录，但不能开始或提交风控复核。</p>
          )}
          {isRisk && detail.application.status === '待风控复核' && (
            <div className="review-section">
              <p>开始后申请将进入“风控复核中”，再填写逐项处理和复核意见。</p>
              <button type="button" className="retry-button" disabled={pending} onClick={() => runAction(onStart)}>
                开始复核
              </button>
            </div>
          )}
          {isRisk && detail.application.status === '风控复核中' && (
            <div className="review-section">
              <h3>逐项人工处理</h3>
              <label>AI 报告总体处理<select value={overallAdoption} onChange={event => setOverallAdoption(event.target.value)}>
                <option value="">请选择</option><option value="accepted">采纳</option><option value="partial">部分采纳</option><option value="rejected">不采纳</option>
              </select></label>
              {latestReport?.analysis_status === 'failed' && (
                <p className="notice">报告处理失败，不能直接完成复核。请核对材料后填写补件原因。</p>
              )}
              {!latestReport && (
                <p className="notice">暂无报告，不能直接完成复核。请核对材料后填写补件原因。</p>
              )}
              {items.map((item) => (
                <fieldset className="review-item" key={item.item_id}>
                  <legend>{item.field_name} · {item.item_id}</legend>
                  <p>{item.reason}</p>
                  <label>
                    处理方式
                    <select
                      value={decisions[item.item_id]?.decision || ''}
                      onChange={(event) => setDecisions((current) => ({
                        ...current,
                        [item.item_id]: { ...current[item.item_id], decision: event.target.value },
                      }))}
                    >
                      <option value="">请选择</option>
                      <option value="accepted">采纳</option>
                      <option value="partial">部分采纳</option>
                      <option value="rejected">不采纳</option>
                    </select>
                  </label>
                  {['partial', 'rejected'].includes(decisions[item.item_id]?.decision) && (
                    <label>
                      修改内容或不采纳原因
                      <textarea
                        value={decisions[item.item_id]?.correctionNote || ''}
                        onChange={(event) => setDecisions((current) => ({
                          ...current,
                          [item.item_id]: { ...current[item.item_id], correctionNote: event.target.value },
                        }))}
                        maxLength={1000}
                      />
                    </label>
                  )}
                </fieldset>
              ))}
              <label className="review-note">
                人工复核意见／补件原因
                <textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} maxLength={2000} />
              </label>
              <div className="page-actions">
                <button
                  type="button"
                  className="retry-button"
                  disabled={pending || !latestReport || latestReport.analysis_status === 'failed'}
                  onClick={() => submit('complete')}
                >完成复核，转待审批</button>
                <button type="button" className="secondary-button" disabled={pending} onClick={() => submit('request_supplement')}>
                  要求补件
                </button>
              </div>
            </div>
          )}
          {actionError && (
            <div className="notice" role="alert">
              <p>{actionError}</p>
              <button type="button" className="text-button" onClick={onRetry}>刷新当前申请</button>
            </div>
          )}
          <div className="review-section">
            <h3>复核记录</h3>
            {(detail.reviews ?? []).length === 0 && <p>暂无已提交的人工复核记录。</p>}
            {(detail.reviews ?? []).map((record) => (
              <article className="record" key={record.review_id}>
                <strong>{resultLabel[record.review_result]}</strong>
                <p>复核人：{record.reviewer_id} · {formatTime(record.reviewed_at)}</p>
                <p>关联报告：{record.report_id || '无可用报告'}</p>
                <p>报告处理：{({ accepted: '采纳', partial: '部分采纳', rejected: '不采纳' })[record.overall_adoption] || '历史记录未填写'}</p>
                <p>意见：{record.review_note}</p>
                {record.item_reviews.map((item) => (
                  <p key={item.item_id}>
                    {item.item_id}：{({ accepted: '采纳', partial: '部分采纳', rejected: '不采纳', confirmed: '确认（历史）', corrected: '修正（历史）' })[item.decision]}
                    {item.correction_note ? ' · ' + item.correction_note : ''}
                  </p>
                ))}
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
