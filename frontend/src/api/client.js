// Minimal API client: JWT storage, auto-refresh on 401, JSON helpers.

const BASE = '/api'

let onLogout = () => {}
export function setLogoutHandler(fn) { onLogout = fn }

export function getTokens() {
  try { return JSON.parse(localStorage.getItem('fl_tokens')) || null } catch { return null }
}

export function setTokens(tokens) {
  if (tokens) localStorage.setItem('fl_tokens', JSON.stringify(tokens))
  else localStorage.removeItem('fl_tokens')
}

async function refreshAccess() {
  const tokens = getTokens()
  if (!tokens?.refresh) return null
  const res = await fetch(`${BASE}/auth/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: tokens.refresh }),
  })
  if (!res.ok) return null
  const data = await res.json()
  const next = { ...tokens, access: data.access, ...(data.refresh ? { refresh: data.refresh } : {}) }
  setTokens(next)
  return next.access
}

export class ApiError extends Error {
  constructor(status, data) {
    super(typeof data === 'string' ? data : data?.error || data?.detail || `Request failed (${status})`)
    this.status = status
    this.data = data
  }
}

async function request(path, { method = 'GET', body, auth = true, retry = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const tokens = getTokens()
    if (tokens?.access) headers.Authorization = `Bearer ${tokens.access}`
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && auth && retry) {
    const access = await refreshAccess()
    if (access) return request(path, { method, body, auth, retry: false })
    setTokens(null)
    onLogout()
  }

  let data = null
  const text = await res.text()
  if (text) { try { data = JSON.parse(text) } catch { data = text } }

  if (!res.ok) throw new ApiError(res.status, data)
  return data
}

export const api = {
  get: (path) => request(path),
  post: (path, body, opts) => request(path, { method: 'POST', body, ...opts }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  del: (path) => request(path, { method: 'DELETE' }),
}

// Pull the most useful error message out of a DRF error payload
export function errorMessage(err, fallback = 'Something went wrong') {
  const d = err?.data
  if (!d) return err?.message || fallback
  if (typeof d === 'string') return d
  if (d.error) return typeof d.error === 'string' ? d.error : JSON.stringify(d.error)
  if (d.detail) return d.detail
  const firstKey = Object.keys(d)[0]
  if (firstKey) {
    const v = d[firstKey]
    const msg = Array.isArray(v) ? v[0] : v
    return firstKey === 'non_field_errors' ? String(msg) : `${firstKey}: ${msg}`
  }
  return err?.message || fallback
}
