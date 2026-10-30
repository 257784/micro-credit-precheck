export async function getJson(path, label, signal) {
  let response;

  try {
    response = await fetch(path, { signal });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error(label + '请求失败，请检查后端服务。');
  }

  if (!response.ok) {
    throw new Error(label + '读取失败（' + response.status + '）');
  }

  try {
    return await response.json();
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error(label + '响应格式错误。');
  }
}

export async function postJson(path, label, role, payload) {
  let response;
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Demo-Role': role,
      },
      body: JSON.stringify(payload ?? {}),
    });
  } catch {
    throw new Error(label + '请求失败，请检查后端服务。');
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const reason = typeof body?.detail === 'string' ? body.detail : '请检查输入或刷新状态。';
    throw new Error(label + '失败（' + response.status + '）：' + reason);
  }
  return response.json();
}

export async function askPolicy(payload, signal) {
  let response;
  try {
    response = await fetch('/api/policy/ask', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('政策问答请求失败，请检查后端服务。');
  }
  if (!response.ok) throw new Error('政策问答请求失败（' + response.status + '）。');
  try {
    const body = await response.json();
    if (typeof body?.status !== 'string' || typeof body?.answer !== 'string' || !Array.isArray(body.sources)) {
      throw new Error('invalid response');
    }
    return body;
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('政策问答响应格式错误。');
  }
}
