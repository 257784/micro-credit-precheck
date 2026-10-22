import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

const seed = JSON.parse(readFileSync(new URL('../../mock_data/seed.json', import.meta.url), 'utf8'));

function detailFor(applicationId) {
  const application = seed.applications.find((item) => item.application_id === applicationId);
  return {
    application,
    enterprise: seed.enterprises.find((item) => item.enterprise_id === application.enterprise_id),
    status_history: seed.status_events.filter((item) => item.application_id === applicationId),
    materials: seed.materials.filter((item) => item.application_id === applicationId),
    reports: seed.reports.filter((item) => item.application_id === applicationId),
  };
}

test('detail page shows application, progress, materials, and clear empty/error states', async () => {
  const server = await createServer({
    root: fileURLToPath(new URL('..', import.meta.url)),
    configFile: false,
    server: { middlewareMode: true },
    appType: 'custom',
  });

  try {
    const { default: ApplicationDetail } = await server.ssrLoadModule('/src/ApplicationDetail.jsx');
    const render = (props) => renderToStaticMarkup(React.createElement(ApplicationDetail, props));
    const complete = render({ detail: detailFor('APP-DEMO-001') });
    assert.match(complete, /经营周转贷（教学产品）/);
    assert.match(complete, /待风控复核/);
    assert.match(complete, /进入待风控复核/);
    assert.match(complete, /青禾经营情况说明.pdf/);
    assert.match(complete, /RPT-DEMO-001/);

    const failed = render({ detail: detailFor('APP-DEMO-003') });
    assert.match(failed, /材料无法解析/);

    const noReport = render({ detail: detailFor('APP-DEMO-004') });
    assert.match(noReport, /暂无报告，不能视为无风险/);

    const noHistory = render({ detail: { ...detailFor('APP-DEMO-004'), status_history: [] } });
    assert.match(noHistory, /暂无进度记录，请人工核实当前状态/);

    const error = render({ detail: null, error: '申请详情读取失败（404）', onRetry: () => {} });
    assert.match(error, /重新加载详情/);
    assert.doesNotMatch(error, /经营周转贷（教学产品）/);

    const { default: App } = await server.ssrLoadModule('/src/App.jsx');
    const previousWindow = globalThis.window;
    try {
      globalThis.window = { location: { search: '?application=APP-DEMO-001' } };
      const directLink = renderToStaticMarkup(React.createElement(App));
      assert.match(directLink, /返回申请列表/);
      assert.match(directLink, /申请详情/);
    } finally {
      if (previousWindow === undefined) delete globalThis.window;
      else globalThis.window = previousWindow;
    }
  } finally {
    await server.close();
  }
});
