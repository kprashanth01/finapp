import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 5000,
})

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
  return 'Could not reach the API. Check that the backend is running.'
}
