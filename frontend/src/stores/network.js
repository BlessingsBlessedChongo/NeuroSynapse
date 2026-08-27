import { defineStore } from 'pinia'
import api, { getStoredToken, registerUnauthorizedHandler, setStoredToken } from '@/services/api'

// Figure 3.2 states
const OPEN_STATUSES = [
  'ANOMALY_DETECTED',
  'MANUAL_REVIEW',
  'READY_FOR_ACTION',
  'SANDBOXING',
  'EXECUTION',
  'VERIFICATION',
]

export const useNetworkStore = defineStore('network', {
  state: () => ({
    // ---- System ----
    loading: false,
    error: null,
    lastUpdated: null,

    // ---- Devices ----
    devices: [],
    deviceTelemetry: {},

    // ---- Dashboard summary ----
    summary: null,

    // ---- Incidents & healing actions ----
    incidents: [],
    healingActions: [],

    // ---- RL Stats ----
    rlStats: null,
    rlError: null,

    // ---- Healing policy configuration ----
    policyConfig: null,
    policyError: null,
    policySaving: false,

    // ---- Telemetry history ----
    telemetryHistory: [],
    telemetryError: null,

    // ---- XAI explanation ----
    xaiExplanation: null,
    xaiLoading: false,
    xaiError: null,
    activeXaiIncidentId: null,

    // ---- Authentication ----
    token: getStoredToken(),
    authenticated: false,
    authenticating: false,
    authError: null,
    adminId: null,
    username: null,
    email: null,
    role: null,

    // ---- Refresh interval ----
    refreshInterval: null,
  }),

  getters: {
    onlineDevices: (state) => state.devices.filter((d) => d.status === 'ONLINE'),
    degradedDevices: (state) => state.devices.filter((d) => d.status === 'DEGRADED'),
    offlineDevices: (state) => state.devices.filter((d) => d.status === 'OFFLINE'),
    deviceCount: (state) => state.summary?.devices?.total ?? state.devices.length,

    openIncidents: (state) => state.summary?.incidents?.open ?? state.incidents.filter(
      (i) => OPEN_STATUSES.includes(i.status)
    ).length,

    totalIncidents: (state) => state.summary?.incidents?.total ?? state.incidents.length,
    resolvedIncidents: (state) => state.summary?.incidents?.by_status?.HEALED ?? 0,

    latestIncidents: (state) =>
      [...state.incidents].sort((a, b) => new Date(b.detected_at) - new Date(a.detected_at)),

    latestIncident(state) {
      return this.latestIncidents[0] || null
    },

    pendingManualReview: (state) => state.incidents.filter((i) => i.status === 'MANUAL_REVIEW'),

    recentHealings: (state) =>
      [...state.healingActions].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),

    overallHealth: (state) => {
      if ((state.summary?.incidents?.open ?? 0) > 0) return 'CRITICAL'
      if (state.devices.some((d) => d.status === 'DEGRADED' || d.status === 'OFFLINE')) {
        return 'WARNING'
      }
      return 'HEALTHY'
    },

    isSuperAdmin: (state) => state.role === 'SUPER_ADMIN',
    canApprove: (state) => state.role === 'SUPER_ADMIN' || state.role === 'ADMIN',
  },

  actions: {
    // ---- Auth ----
    async checkAuth() {
      if (!this.token) {
        this.authenticated = false
        return
      }
      try {
        const response = await api.currentAdmin()
        this._applyAdminProfile(response.data)
        this.authenticated = true
        this.authError = null
      } catch {
        this._clearAuth()
      }
    },

    async login(username, password) {
      this.authenticating = true
      this.authError = null
      try {
        const response = await api.login({ username, password })
        const { token, admin } = response.data
        setStoredToken(token)
        this.token = token
        this._applyAdminProfile(admin)
        this.authenticated = true
        return true
      } catch (err) {
        this.authError = err.response?.data?.error || 'Login failed.'
        this._clearAuth()
        return false
      } finally {
        this.authenticating = false
      }
    },

    async logout() {
      try {
        await api.logout()
      } catch {
        // ignore
      } finally {
        this._clearAuth()
      }
    },

    _applyAdminProfile(admin) {
      this.adminId = admin?.admin_id ?? null
      this.username = admin?.username ?? null
      this.email = admin?.email ?? null
      this.role = admin?.role ?? null
    },

    _clearAuth() {
      setStoredToken(null)
      this.token = null
      this.authenticated = false
      this.adminId = null
      this.username = null
      this.email = null
      this.role = null
    },

    // ---- Summary (NOW populates incidents + healings) ----
    async fetchSummary() {
      try {
        this.loading = true
        const response = await api.getSummary()
        this.summary = response.data
        this.lastUpdated = new Date()

        // Populate incidents from summary as fallback
        if (response.data.recent_incidents) {
          this.incidents = response.data.recent_incidents
        }
        if (response.data.recent_healing_actions) {
          this.healingActions = response.data.recent_healing_actions
        }

        this.error = null
      } catch (err) {
        this.error = 'Failed to fetch dashboard summary: ' + err.message
        console.error(this.error, err)
      } finally {
        this.loading = false
      }
    },

    // ---- Devices ----
    async fetchDevices() {
      try {
        const response = await api.getDevices()
        const data = response.data
        this.devices = Array.isArray(data) ? data : data.results || []
        this.error = null
      } catch (err) {
        this.error = 'Failed to fetch devices: ' + err.message
      }
    },

    // ---- Telemetry ----
    async fetchTelemetry() {
      try {
        this.telemetryError = null
        const response = await api.getTelemetry()
        const telemetryData = response.data.telemetry || []

        const timestampMap = new Map()
        const deviceLatest = {}

        telemetryData.forEach((deviceGroup) => {
          const records = deviceGroup.records || []
          records.forEach((record) => {
            const key = record.timestamp
            if (!timestampMap.has(key)) timestampMap.set(key, [])
            timestampMap.get(key).push({
              cpu_usage: parseFloat(record.cpu) || 0,
              memory_usage: parseFloat(record.memory) || 0,
              packet_loss: parseFloat(record.packet_loss) || 0,
            })
          })
          if (records[0]) {
            deviceLatest[deviceGroup.device] = {
              cpu: parseFloat(records[0].cpu) || 0,
              memory: parseFloat(records[0].memory) || 0,
              packet_loss: parseFloat(records[0].packet_loss) || 0,
              timestamp: records[0].timestamp,
            }
          }
        })

        const avgPoints = Array.from(timestampMap.entries())
          .map(([timestamp, records]) => {
            const count = records.length
            return {
              timestamp,
              cpu_usage: records.reduce((s, r) => s + r.cpu_usage, 0) / count,
              memory_usage: records.reduce((s, r) => s + r.memory_usage, 0) / count,
              packet_loss: records.reduce((s, r) => s + r.packet_loss, 0) / count,
            }
          })
          .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))

        this.telemetryHistory = avgPoints.slice(-30)
        this.deviceTelemetry = deviceLatest
      } catch (err) {
        this.telemetryError = 'Failed to load telemetry.'
      }
    },

    // ---- Incidents ----
    async fetchIncidents(params = {}) {
      try {
        const response = await api.getIncidents(params)
        const data = response.data || []
        this.incidents = data.length > 0 ? data : this._fallbackIncidentsFromSummary()
        this.error = null
      } catch (err) {
        const fallback = this._fallbackIncidentsFromSummary()
        if (fallback.length > 0) {
          this.incidents = fallback
          this.error = null
        } else {
          this.error = 'Failed to fetch incidents: ' + err.message
        }
      }
    },

    _fallbackIncidentsFromSummary() {
      return this.summary?.recent_incidents || []
    },

    async fetchIncidentDetail(incidentId, force = false) {
      if (!incidentId) return null
      if (!force && incidentId === this.activeXaiIncidentId && this.xaiExplanation) {
        return this.xaiExplanation
      }

      this.xaiLoading = true
      this.xaiError = null
      try {
        const response = await api.getIncidentDetail(incidentId)
        this.xaiExplanation = response.data?.xai_explanation || null
        this.activeXaiIncidentId = incidentId
        return response.data
      } catch (err) {
        this.xaiExplanation = null
        this.xaiError = 'Unable to load diagnosis explanation.'
        return null
      } finally {
        this.xaiLoading = false
      }
    },

    async approveIncident(incidentId) {
      await api.approveIncident(incidentId)
      await this.refreshAll()
    },

    async rejectIncident(incidentId) {
      await api.rejectIncident(incidentId)
      await this.refreshAll()
    },

    async rollbackIncident(incidentId) {
      await api.rollbackIncident(incidentId)
      await this.refreshAll()
    },

    // ---- Healing actions ----
    async fetchHealingActions(params = {}) {
      try {
        const response = await api.getHealingActions(params)
        const data = response.data || []
        this.healingActions = data.length > 0 ? data : this._fallbackHealingActionsFromSummary()
      } catch (err) {
        const fallback = this._fallbackHealingActionsFromSummary()
        if (fallback.length > 0) {
          this.healingActions = fallback
        }
      }
    },

    _fallbackHealingActionsFromSummary() {
      return this.summary?.recent_healing_actions || []
    },

    async fetchHealingActionDetail(healingActionId) {
      if (!healingActionId) return null
      try {
        const response = await api.getHealingActionDetail(healingActionId)
        return response.data || null
      } catch (err) {
        console.error('Failed to fetch healing action detail:', err)
        return null
      }
    },

    // ---- RL stats ----
    async fetchRLStats() {
      try {
        this.rlError = null
        const response = await api.getRLStats()
        this.rlStats = response.data
      } catch (err) {
        this.rlStats = null
        this.rlError = 'Failed to load RL stats.'
      }
    },

    // ---- Policy config ----
    async fetchPolicyConfig() {
      try {
        this.policyError = null
        const response = await api.getPolicyConfig()
        this.policyConfig = response.data
      } catch (err) {
        this.policyConfig = null
        this.policyError = 'Failed to load policy.'
      }
    },

    async updatePolicyConfig(payload) {
      this.policySaving = true
      try {
        const response = await api.updatePolicyConfig(payload)
        this.policyConfig = response.data
        return true
      } catch (err) {
        this.policyError = err.response?.data?.detail || 'Failed to save policy.'
        return false
      } finally {
        this.policySaving = false
      }
    },

    // ---- Auto-refresh ----
    async refreshAll() {
      await Promise.all([
        this.fetchSummary(),
        this.fetchDevices(),
        this.fetchTelemetry(),
        this.fetchIncidents(),
        this.fetchHealingActions(),
      ])
      if (this.latestIncident?.id) {
        await this.fetchIncidentDetail(this.latestIncident.id)
      }
    },

    async startAutoRefresh(intervalMs = 2000) {
      this.stopAutoRefresh()
      await this.refreshAll()
      this.refreshInterval = setInterval(() => this.refreshAll(), intervalMs)
    },

    stopAutoRefresh() {
      if (this.refreshInterval) {
        clearInterval(this.refreshInterval)
        this.refreshInterval = null
      }
    },
  },
})

registerUnauthorizedHandler(() => {
  const store = useNetworkStore()
  store.stopAutoRefresh()
  store._clearAuth()
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
})