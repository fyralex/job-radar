import {defineConfig} from 'vitest/config';

// Kept apart from vite.config.ts: vitest ships its own copy of vite, whose
// plugin types don't match the app's.
export default defineConfig({
  esbuild: {jsx: 'automatic'},
  test: {
    environment: 'jsdom',
    setupFiles: ['src/__tests__/setup.ts'],
  },
});
