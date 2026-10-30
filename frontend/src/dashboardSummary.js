export const applicationStatusLabels = [
  '待风控复核',
  '风控复核中',
  '待企业补充材料',
  '待审批',
];

export const reportStatusLabels = [
  { key: 'needs_human_review', label: '待人工核验' },
  { key: 'failed', label: '解析失败' },
  { key: 'missing', label: '暂无报告' },
];

export function summarizeApplications(applications) {
  const applicationCounts = Object.fromEntries(
    applicationStatusLabels.map((status) => [status, 0]),
  );
  const reportCounts = Object.fromEntries(
    reportStatusLabels.map(({ key }) => [key, 0]),
  );
  applicationCounts.other = 0;
  reportCounts.other = 0;

  for (const application of applications) {
    if (Object.hasOwn(applicationCounts, application.status)) {
      applicationCounts[application.status] += 1;
    } else {
      applicationCounts.other += 1;
    }
    const reportStatus = application.report_status ?? 'missing';
    if (Object.hasOwn(reportCounts, reportStatus)) {
      reportCounts[reportStatus] += 1;
    } else {
      reportCounts.other += 1;
    }
  }

  return { total: applications.length, applicationCounts, reportCounts };
}
