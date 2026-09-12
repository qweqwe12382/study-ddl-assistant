/** Keep local development cookies on the page host; preserve deployed endpoints. */
export function resolveApiBaseUrl(configured, hostname, development) {
  const base = configured || 'http://127.0.0.1:8000/api'
  if (!development || !['localhost', '127.0.0.1'].includes(hostname)) return base
  try {
    const url = new globalThis.URL(base)
    if (url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname)) {
      url.hostname = hostname
      return url.toString()
    }
  } catch {
    // Relative deployment paths and invalid settings retain their original handling.
  }
  return base
}
