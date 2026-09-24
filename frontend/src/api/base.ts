/** Vite embeds the public backend URL at build time. No secrets belong here.
 * Without it, retain the local /api proxy to http://127.0.0.1:8000.
 */
export function apiUrl(path: string, configuredBase = import.meta.env?.VITE_API_BASE_URL): string {
  if (!path.startsWith('/') || path.startsWith('//')) throw new Error('API paths must start with one slash')
  const base = configuredBase?.trim().replace(/\/+$/, '')
  if (!base) return `/api${path}`
  const parsed = new URL(base)
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.search || parsed.hash || parsed.username || parsed.password) {
    throw new Error('VITE_API_BASE_URL must be an HTTP(S) backend URL without credentials, query or fragment')
  }
  return `${base}${path}`
}
