import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api': {
          target: env.BACKEND_URL || 'http://127.0.0.1:8000',
          // 保留浏览器访问前端时的 Host，供后端校验 Origin。
          changeOrigin: false,
        },
      },
    },
  };
});
