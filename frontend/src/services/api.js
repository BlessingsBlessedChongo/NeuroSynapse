import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const TOKEN_STORAGE_KEY = 'neurosynapse_token'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ---------------------------------------------------------------------------
// Token storage helpers
// The backend uses DRF TokenAuthentication (Authorization: Token <key>),
// not session cookies, so the token is persisted in localStorage and
// attached to every outgoing request via an interceptor.
// ---------------------------------------------------------------------------
export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function setStoredToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  }
}

api.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})

// Notify listeners (the Pinia store) when the server tells us the token is
// no longer valid, so the app can drop back to the login screen cleanly.
let onUnauthorized = null
export function registerUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

// Guard so multiple simultaneous 401s don't trigger repeated logout calls.
let isHandlingUnauthorized = false

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status
    const config = error.config || {}

    // For blob requests (e.g. log downloads), error bodies arrive as Blobs.
    // Parse them so downstream consumers can read a real error message.
    if (config.responseType === 'blob' && error.response?.data instanceof Blob) {
      try {
        const text = await error.response.data.text()
        error.response.data = text ? JSON.parse(text) : {}
      } catch {
        // Response wasn't JSON; leave the Blob in place.
      }
    }

    // Never treat a failed login attempt as a session expiry.
    const isAuthEndpoint =
      typeof config.url === 'string' &&
      (config.url.includes('/api/auth/login/') || config.url.includes('/api/auth/logout/'))

    if (status === 401 && !isAuthEndpoint && onUnauthorized && !isHandlingUnauthorized) {
      isHandlingUnauthorized = true
      try {
        onUnauthorized()
      } finally {
        // Release the guard on the next tick so the store has time to react.
        setTimeout(() => {
          isHandlingUnauthorized = false
        }, 1000)
      }
    }

    return Promise.reject(error)
  },
)

export default {
  // ---- Health ----
  healthCheck() {
    return api.get('/api/health/')
  },

  // ---- Authentication ----
  login(credentials) {
    return api.post('/api/auth/login/', credentials)
  },

  logout() {
    return api.post('/api/auth/logout/')
  },

  currentAdmin() {
    return api.get('/api/auth/me/')
  },

  // ---- Telemetry ----
  getTelemetry() {
    return api.get('/api/telemetry/')
  },

  // ---- Devices ----
  getDevices() {
    return api.get('/api/devices/')
  },

  createDevice(payload) {
    return api.post('/api/devices/', payload)
  },

  updateDevice(id, payload) {
    return api.patch(`/api/devices/${id}/`, payload)
  },

  deleteDevice(id) {
    return api.delete(`/api/devices/${id}/`)
  },

  // ---- Dashboard summary / alerts ----
  getSummary() {
    return api.get('/api/dashboard/summary/')
  },

  getAlerts() {
    return api.get('/api/dashboard/alerts/')
  },

  // ---- Incidents ----
  getIncidents(params = {}) {
    return api.get('/api/dashboard/incidents/', { params })
  },

  getIncidentDetail(incidentId) {
    return api.get(`/api/dashboard/incidents/${incidentId}/`)
  },

  downloadIncidentLog(incidentId) {
    return api.get(`/api/incidents/${incidentId}/log/`, {
      responseType: 'blob',
    })
  },

  // Approve / reject / rollback run the full MAPE-K execution path
  // synchronously on the backend (sandbox validation, healing dispatch,
  // ~2s verification delay, RL reward write, incident log generation).
  // The default 15s axios timeout can be exceeded on slow disks or under
  // SQLite lock contention, so these three use a 45s timeout.
  approveIncident(incidentId) {
    return api.post(
      `/api/dashboard/incidents/${incidentId}/approve/`,
      { approved: true },
      { timeout: 45000 },
    )
  },

  rejectIncident(incidentId) {
    return api.post(
      `/api/dashboard/incidents/${incidentId}/approve/`,
      { approved: false },
      { timeout: 45000 },
    )
  },

  rollbackIncident(incidentId) {
    return api.post(
      `/api/dashboard/incidents/${incidentId}/rollback/`,
      {},
      { timeout: 45000 },
    )
  },

  // ---- Healing actions ----
  getHealingActions(params = {}) {
    return api.get('/api/dashboard/healing-actions/', { params })
  },

  getHealingActionDetail(healingActionId) {
    return api.get(`/api/dashboard/healing-actions/${healingActionId}/`)
  },

  // ---- RL agent stats ----
  getRLStats() {
    return api.get('/api/dashboard/rl-stats/')
  },

  // ---- Healing policy configuration (UC-01) ----
  getPolicyConfig() {
    return api.get('/api/dashboard/policy/')
  },

  updatePolicyConfig(payload) {
    return api.put('/api/dashboard/policy/', payload)
  },
}