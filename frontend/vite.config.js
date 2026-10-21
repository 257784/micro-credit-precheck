import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api': env.BACKEND_URL || 'http://127.0.0.1:8000',
      },
    },
  };
});
