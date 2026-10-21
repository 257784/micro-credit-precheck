export function filterApplications(applications, searchText, status) {
  const keyword = searchText.trim().toLowerCase();

  return applications.filter((application) => {
    const matchesText =
      keyword === '' ||
      application.application_id.toLowerCase().includes(keyword) ||
      application.enterprise_name.toLowerCase().includes(keyword);
    const matchesStatus = status === '' || application.status === status;

    return matchesText && matchesStatus;
  });
}
