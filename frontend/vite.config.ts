import react from '@vitejs/plugin-react';
import {defineConfig} from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    // `yarn dev` proxies the API to a backend on localhost:8000.
    proxy: {'/api': 'http://localhost:8000'},
  },
});
