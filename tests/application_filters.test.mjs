import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { filterApplications } from '../frontend/src/applicationFilters.js';

const seedUrl = new URL('../mock_data/seed.json', import.meta.url);
const seed = JSON.parse(readFileSync(fileURLToPath(seedUrl), 'utf8'));
const enterprises = new Map(
  seed.enterprises.map((enterprise) => [
    enterprise.enterprise_id,
    enterprise.enterprise_name,
  ]),
);
const applications = seed.applications.map((application) => ({
  ...application,
  enterprise_name: enterprises.get(application.enterprise_id),
}));

test('searches application ID and enterprise name', () => {
  assert.deepEqual(
    filterApplications(applications, ' app-demo-002 ', '').map(
      (application) => application.application_id,
    ),
    ['APP-DEMO-002'],
  );
  assert.deepEqual(
    filterApplications(applications, '星桥', '').map(
      (application) => application.application_id,
    ),
    ['APP-DEMO-002'],
  );
});

test('combines status selection with text and handles empty results', () => {
  assert.equal(filterApplications(applications, '', '待风控复核').length, 4);
  assert.equal(filterApplications(applications, 'APP-NOT-FOUND', '').length, 0);

  const mixedStatuses = [
    ...applications,
    { ...applications[0], application_id: 'APP-DEMO-005', status: '待审批' },
  ];
  assert.deepEqual(
    filterApplications(mixedStatuses, '青禾', '待审批').map(
      (application) => application.application_id,
    ),
    ['APP-DEMO-005'],
  );
});
