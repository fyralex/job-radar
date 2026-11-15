import js from '@eslint/js';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {ignores: ['dist']},
  js.configs.recommended,
  ...tseslint.configs.strict,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {globals: globals.browser},
    settings: {react: {version: '19'}},
    plugins: {react, 'react-hooks': reactHooks, 'react-refresh': reactRefresh},
    rules: {
      ...react.configs.recommended.rules,
      ...react.configs['jsx-runtime'].rules,
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', {allowConstantExport: true}],
      // RTK Query endpoints use `void` for "no argument".
      '@typescript-eslint/no-invalid-void-type': 'off',
    },
  },
);
