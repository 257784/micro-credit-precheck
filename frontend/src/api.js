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
