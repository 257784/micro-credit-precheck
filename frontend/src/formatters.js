const amountFormatter = new Intl.NumberFormat('zh-CN');

export function formatAmount(amount) {
  return '¥' + amountFormatter.format(amount);
}

export function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—';
}

export function reportLabel(status) {
  // 处理失败和无报告都需要显式提示，不能被当作“没有关注项”。
  if (status === 'failed') return '解析失败';
  if (status === 'needs_human_review') return '待人工核验';
  return status || '暂无报告';
}

export function knowledgeLabel(reference) {
  if (!reference) return '无适用依据';
  return (
    reference.knowledge_id +
    ' / ' +
    reference.version +
    ' · ' +
    reference.requirement
  );
}
