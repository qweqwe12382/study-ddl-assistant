import vue from 'eslint-plugin-vue'

export default [
  {
    ignores: ['dist/**'],
  },
  ...vue.configs['flat/essential'],
  {
    files: ['**/*.js', '**/*.vue'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        console: 'readonly',
        window: 'readonly',
        document: 'readonly',
        fetch: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        navigator: 'readonly',
        performance: 'readonly',
        ResizeObserver: 'readonly',
        requestAnimationFrame: 'readonly',
        HTMLElement: 'readonly',
        File: 'readonly',
      },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-undef': 'error',
      'no-unreachable': 'error',
    },
  },
  {
    files: ['**/*.vue'],
    rules: { 'vue/no-undef-properties': 'error' },
  },
  {
    files: ['src/components/AcademicEntryForms.vue', 'src/components/PasteNoticeDialog.vue'],
    // These form fragments intentionally edit the parent's unsaved draft.
    // Replacing the draft prop itself must still be rejected.
    rules: { 'vue/no-mutating-props': ['error', { shallowOnly: true }] },
  },
]
