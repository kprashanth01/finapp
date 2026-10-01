import axios from 'axios'
import { identityEpoch } from './authState.js'

export function defaultApiBaseUrl(page = typeof window === 'undefined'
  ? { protocol: 'http:', hostname: 'localhost' } : window.location) {
  return `${page.protocol}//${page.hostname}:8000`
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl(),
  timeout: 5000,
  withCredentials: true,
  headers: { 'X-FinApp-Request': '1' },
})

api.interceptors.request.use((config) => {
  config.finappIdentityEpoch = identityEpoch.current()
  return config
})

api.interceptors.response.use((response) => response, (error) => {
  const path = error.config?.url ?? ''
  if (error.response?.status === 401 && !['/auth/login', '/auth/claim', '/auth/me'].includes(path) &&
      error.config?.finappIdentityEpoch === identityEpoch.current() && typeof window !== 'undefined') {
    window.dispatchEvent(new Event('finapp:session-expired'))
  }
  return Promise.reject(error)
})

export async function getCurrentUser() { return (await api.get('/auth/me')).data }
export async function signIn(values) { return (await api.post('/auth/login', values)).data }
export async function claimEarlierProfile(values) { return (await api.post('/auth/claim', values)).data }
export async function signOut() { await api.post('/auth/logout') }

export async function getHealth(signal) {
  const response = await api.get('/health', { signal })
  return response.data
}

export async function createUser(user) {
  const response = await api.post('/users', user)
  return response.data
}

export async function getUser(userId) {
  const response = await api.get(`/users/${userId}`)
  return response.data
}

export async function updateUser(userId, user) {
  const response = await api.put(`/users/${userId}`, user)
  return response.data
}

export async function getFinancialProfile(userId) {
  const response = await api.get(`/users/${userId}/financial-profile`)
  return response.data
}

export async function getFinancialAnalysis(userId) {
  const response = await api.get(`/users/${userId}/financial-analysis`)
  return response.data
}

export async function saveFinancialProfile(userId, profile) {
  const response = await api.put(`/users/${userId}/financial-profile`, profile)
  return response.data
}

export async function getLatestAdvisorySession(userId) {
  const response = await api.get(`/users/${userId}/advisory-sessions/latest`)
  return response.data
}

export async function getAdvisorySessionHistory(userId, { limit = 10, beforeId } = {}) {
  const response = await api.get(`/users/${userId}/advisory-sessions`, {
    params: { limit, ...(beforeId == null ? {} : { before_id: beforeId }) },
  })
  return response.data
}

export async function getAdvisorySession(userId, sessionId) {
  const response = await api.get(`/users/${userId}/advisory-sessions/${sessionId}`)
  return response.data
}

export async function runAdvisorySession(userId) {
  const response = await api.post(`/users/${userId}/advisory-sessions`)
  return response.data
}

export async function compareResearchPolicies(userId, seed = 42) {
  const response = await api.post(`/users/${userId}/research/comparison`, { seed })
  return response.data
}

export async function explainSavedSession(userId, sessionId) {
  return (await api.post(`/users/${userId}/advisory-sessions/${sessionId}/reasoning`, {}, { timeout: 20000 })).data
}

export async function explainLiveRun(userId, result) {
  return (await api.post(`/users/${userId}/research/orchestration-reasoning`, {
    mode: result.mode, seed: result.seed ?? 42,
    state_fingerprint: result.state_fingerprint, action: result.action,
  }, { timeout: 30000 })).data
}

export async function runOrchestration(userId, mode, seed = 42) {
  return (await api.post(`/users/${userId}/research/orchestration-run`, {
    ...(mode === 'configured' ? {} : { mode }), seed,
  }, {
    timeout: ['rl', 'trained_rl', 'configured'].includes(mode) ? 30000 : 5000,
  })).data
}

export async function getResearchActions(userId) {
  return (await api.get(`/users/${userId}/research/actions`)).data
}

export async function getResearchTrainingEvidence(userId) {
  return (await api.get(`/users/${userId}/research/training-evidence`)).data
}

export async function getResearchEvaluation(userId) {
  return (await api.get(`/users/${userId}/research/evaluation`)).data
}

export async function runManualResearchAction(userId, selectedAgents) {
  return (await api.post(`/users/${userId}/research/manual-action`, {
    selected_agents: selectedAgents,
  })).data
}

export async function getGoals(userId, { includeArchived = false } = {}) {
  return (await api.get(`/users/${userId}/goals`, { params: { include_archived: includeArchived } })).data
}

export async function createGoal(userId, values) {
  return (await api.post(`/users/${userId}/goals`, values)).data
}

export async function updateGoal(userId, goalId, values) {
  return (await api.put(`/users/${userId}/goals/${goalId}`, values)).data
}

export async function setGoalArchived(userId, goalId, archived) {
  return (await api.patch(`/users/${userId}/goals/${goalId}`, { archived })).data
}

export function explainApiError(error) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const field = String(detail[0].loc?.at(-1) ?? 'Input').replaceAll('_', ' ')
    return `${field}: ${detail[0].msg}`
  }
  if (error.response) return 'The API could not complete the request. Check the backend terminal and database setup.'
  if (error.code === 'ECONNABORTED') return 'The request timed out. The trained selector may still be loading; retry in a moment.'
  return 'Could not reach the API. Check that the backend is running.'
}
