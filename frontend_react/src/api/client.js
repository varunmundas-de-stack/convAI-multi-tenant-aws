import axios from 'axios'

const api = axios.create({ baseURL: '/' })

export async function loginUser(username, password) {
  const { data } = await api.post('/login', { username, password })
  return data
}

export async function logoutUser() {
  await api.get('/logout')
}

export async function fetchSuggestions() {
  const { data } = await api.get('/api/suggestions')
  return data.suggestions || []
}

export async function sendQuery(question) {
  const { data } = await api.post('/api/query', { question })
  return data
}

export async function fetchInsights() {
  const { data } = await api.get('/api/insights')
  return data.insights || []
}

export async function fetchInsightCount() {
  const { data } = await api.get('/api/insights/count')
  return data.unread_count || 0
}

export async function markInsightRead(insightId) {
  await api.post(`/api/insights/${insightId}/read`)
}

// ── Chat Sessions ──────────────────────────────────────────────
export async function fetchSessions() {
  const { data } = await api.get('/api/sessions')
  return data.sessions || []
}

export async function createSession(title = 'New conversation') {
  const { data } = await api.post('/api/sessions', { title })
  return data  // { session_id, title }
}

export async function renameSession(sessionId, title) {
  const { data } = await api.patch(`/api/sessions/${sessionId}`, { title })
  return data
}

export async function deleteSession(sessionId) {
  await api.delete(`/api/sessions/${sessionId}`)
}

export async function fetchSessionMessages(sessionId) {
  const { data } = await api.get(`/api/sessions/${sessionId}/messages`)
  return data.messages || []
}

export async function saveMessage(sessionId, { role, content, raw_data, query_type, metadata, title_hint }) {
  const { data } = await api.post(`/api/sessions/${sessionId}/messages`, {
    role, content, raw_data, query_type, metadata, title_hint,
  })
  return data  // { message_id }
}
