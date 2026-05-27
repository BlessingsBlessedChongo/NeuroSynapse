import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
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

  // Health check
  healthCheck() {
    return api.get('/api/health/')
  },
}