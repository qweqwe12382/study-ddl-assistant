import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: '127.0.0.1',
  },
  optimizeDeps: {
    // Avoid esbuild's dependency discovery scan on the current Windows
    // environment; Vite will transform dependencies on demand instead.
    noDiscovery: true,
    include: [
      'dayjs',
      'dayjs/plugin/advancedFormat.js',
      'dayjs/plugin/customParseFormat.js',
      'dayjs/plugin/dayOfYear.js',
      'dayjs/plugin/isSameOrAfter.js',
      'dayjs/plugin/isSameOrBefore.js',
      'dayjs/plugin/localeData.js',
      'dayjs/plugin/weekOfYear.js',
      'dayjs/plugin/weekYear.js',
    ],
  },
})
