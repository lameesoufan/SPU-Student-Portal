import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

const srcDir = fileURLToPath(new URL('./src/', import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      '@': srcDir,
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setupUi.js'],
    testTimeout: 10000,

    include: [
      'src/**/*.ui.test.{js,jsx}',
      'src/**/*.role-ui.test.{js,jsx}',
      'src/**/*.academic-ui.test.{js,jsx}',
      'src/**/*.student-ui.test.{js,jsx}',
      'src/**/*.final-ui.test.{js,jsx}',
    ],

    restoreMocks: true,
    clearMocks: true,
  },
});