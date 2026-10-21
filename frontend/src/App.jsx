import { useEffect, useState } from 'react';

export default function App() {
  const [apiStatus, setApiStatus] = useState('检查中…');

  useEffect(() => {
    const controller = new AbortController();

    fetch('/api/health', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('接口响应异常');
        return response.json();
      })
      .then((data) => setApiStatus(data.status === 'ok' ? '已连接' : '响应异常'))
      .catch((error) => {
        if (error.name !== 'AbortError') setApiStatus('未连接，请启动后端');
      });

    return () => controller.abort();
  }, []);

  return (
    <main style={{ maxWidth: 720, margin: '80px auto', padding: '0 24px', fontFamily: 'sans-serif' }}>
      <p>F2 · 本地开发环境</p>
      <h1>小微企业授信智能预审系统</h1>
      <p>工程首页已启动。下一步将实现授信申请列表。</p>
      <p role="status">后端服务：{apiStatus}</p>
    </main>
  );
}
