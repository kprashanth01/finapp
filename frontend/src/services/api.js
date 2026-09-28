import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 5000,
})

export async function getHealth(signal) {
  const response = await api.get('/health', { signal })
  return response.data
}
