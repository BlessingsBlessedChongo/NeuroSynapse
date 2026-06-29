import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

export default {
  // System status
  getStatus() {
    return api.get('/api/status/')
  },

  // Telemetry data
  getTelemetry() {
    return api.get('/api/telemetry/')
  },

  // Incidents
  getIncidents() {
    return api.get('/api/incidents/')
  },

  // RL Agent stats
  getRLStats() {
    return api.get('/api/rl-stats/')
  },

  // XAI explanations
  getDiagnosisExplanation(incidentId) {
    return api.get(`/api/xai/diagnosis/${incidentId}/`)
  },

  getHealingExplanation(healingId) {
    return api.get(`/api/xai/healing/${healingId}/`)
  },

  // Manual healing approval/rejection
  approveHealing(incidentId) {
    return api.post(`/api/incidents/${incidentId}/approve/`, {})
  },

  rejectHealing(incidentId) {
    return api.post(`/api/incidents/${incidentId}/reject/`, {})
  },

  // Authentication
  login(credentials) {
    return api.post('/api/auth/login/', credentials)
  },

  logout() {
    return api.post('/api/auth/logout/')
  },

  authStatus() {
    return api.get('/api/auth/status/')
  },

  // Health check
  healthCheck() {
    return api.get('/api/health/')
  },
}