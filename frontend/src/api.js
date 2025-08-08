
const API_BASE = import.meta.env.VITE_API_BASE || ''
async function request(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, { headers: { 'Content-Type': 'application/json', ...(opts.headers||{}) }, ...opts })
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try { const body = await res.json(); msg = body.error || msg } catch {}
    throw new Error(msg)
  }
  return res.json()
}
export const api = {
  state: () => request('/api/state'),
  next: (people) => { const p = new URLSearchParams(); (people||[]).forEach(x=>p.append('people',x)); return request(`/api/next?${p.toString()}`) },
  run: (people) => request('/api/run', { method:'POST', body: JSON.stringify({ people }) }),
  setPrice: (name, price) => request('/api/set-price', { method:'POST', body: JSON.stringify({ name, price }) }),
  removePerson: (name) => request('/api/remove-person', { method:'POST', body: JSON.stringify({ name }) }),
  resetBalances: () => request('/api/reset-balances', { method:'POST' }),
}
