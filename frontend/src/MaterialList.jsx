import React, { useState } from 'react';
import { formatTime } from './formatters.js';
import MaterialCheck from './MaterialCheck.jsx';
import DocumentUpload from './DocumentUpload.jsx';

export default function MaterialList({ detail, error, loading, onRetry, onOpenReport, requestedMaterialId }) {
  const [selectedMaterialId, setSelectedMaterialId] = useState(requestedMaterialId ?? null);
  const materials = [...(detail?.materials ?? [])].sort((left, right) =>
    left.material_type.localeCompare(right.material_type, 'zh-CN') ||
    right.version_no - left.version_no ||
    right.submitted_at.localeCompare(left.submitted_at),
  );
  const selected = materials.find((item) => item.material_id === selectedMaterialId) ?? materials[0];
  const evidence = (detail?.reports ?? []).flatMap((report) =>
    report.items.flatMap((item) =>
      item.evidence
        .filter((ref) => ref.material_id === selected?.material_id)
        .map((ref) => ({ ...ref, report_id: report.report_id })),
    ),
  );
  const referencedIds = new Set(
    (detail?.reports ?? []).flatMap((report) =>
      report.items.flatMap((item) => item.evidence.map((ref) => ref.material_id)),
    ),
  );

  return (
    <section className="panel materials-page" aria-labelledby="materials-heading">
      <h2 id="materials-heading">申请材料清单</h2>
      {loading && <p role="status">正在读取材料…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button type="button" className="retry-button" onClick={onRetry}>重新加载材料</button>
        </div>
      )}
      {detail && (
        <>
          <p className="materials-context">
            {detail.enterprise.enterprise_name} · {detail.application.application_id}
          </p>
          <p className="helper-text">以下为虚构教学数据。静态摘录仅供核对流程演示，不能替代 PDF/DOCX 正式原件。</p>
          <MaterialCheck key={detail.application.application_id} applicationId={detail.application.application_id} />
          <DocumentUpload key={'upload-'+detail.application.application_id} applicationId={detail.application.application_id} />
          <button type="button" className="secondary-button" onClick={onOpenReport}>
            查看本申请的 AI 预审报告 →
          </button>
          {materials.length === 0 ? (
            <p className="notice">暂无申请材料，请联系客户经理核实并补交。</p>
          ) : (
            <div className="materials-layout">
              <div className="materials-cards" aria-label="材料及版本">
                {materials.map((material) => (
                  <button
                    type="button"
                    className={'material-card' + (material.material_id === selected?.material_id ? ' selected' : '')}
                    key={material.material_id}
                    onClick={() => setSelectedMaterialId(material.material_id)}
                    aria-pressed={material.material_id === selected?.material_id}
                  >
                    <span className="material-card-top">
                      <strong>{material.material_type}</strong>
                      <span>第 {material.version_no} 版</span>
                    </span>
                    <span className="material-filename">{material.file_name}</span>
                    <span>解析/初检：{material.check_status}</span>
                    <span>提交于 {formatTime(material.submitted_at)}</span>
                    {referencedIds.has(material.material_id) && <span className="material-reference">报告引用此版本</span>}
                  </button>
                ))}
              </div>
              <section className="material-preview" aria-labelledby="preview-heading">
                <h3 id="preview-heading">材料查看</h3>
                <p><strong>{selected.file_name}</strong> · 第 {selected.version_no} 版</p>
                <p>材料编号：{selected.material_id}</p>
                {selected.check_status === '解析失败' ? (
                  <p className="notice">材料解析失败，无法查看摘录。请人工核对文件，并联系客户经理补交可读取的 PDF/DOCX。</p>
                ) : selected.sample_excerpt ? (
                  <div className="sample-excerpt">
                    <strong>{selected.sample_location}</strong>
                    <p>{selected.sample_excerpt}</p>
                    <small>教学静态摘录，不是原件；页码和文字须以正式材料核对。</small>
                  </div>
                ) : (
                  <p className="notice">暂无教学摘录或样例文件，请人工查看正式原件。</p>
                )}
                {evidence.length > 0 && (
                  <div className="material-evidence">
                    <h4>报告中的证据定位</h4>
                    {evidence.map((ref, index) => (
                      <p key={ref.report_id + '-' + index}>
                        {ref.report_id} · 第 {ref.page} 页 · “{ref.quote}”
                      </p>
                    ))}
                    <small>报告引用只说明来源，不代表已人工确认。</small>
                  </div>
                )}
              </section>
            </div>
          )}
        </>
      )}
    </section>
  );
}
