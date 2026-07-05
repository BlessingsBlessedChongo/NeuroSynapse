import { defineStore } from 'pinia'
import api from '@/services/api'

export const useNetworkStore = defineStore('network', {
  state: () => ({
    // System
    systemStatus: 'HEALTHY',
    loading: false,
    error: null,
    lastUpdated: null,

    // Devices
    devices: [],

    // Stats
    deviceCount: 0,
    openIncidents: 0,
    healedToday: 0,
    totalIncidents: 0,

    // Incidents & Healings
    latestIncidents: [],
    recentHealings: [],

    // RL Stats
    rlStats: null,
    rlError: null,

    // Telemetry history
    telemetryHistory: [],
    telemetryError: null,

    // XAI explanation
    xaiExplanation: null,
    xaiLoading: false,
    xaiError: null,
    activeXaiIncidentId: null,

    // Authentication
    authenticated: false,
    authenticating: false,
    authError: null,
    username: null,
    isAdmin: false,

    // Refresh interval
    refreshInterval: null,
  }),

  getters: {
    criticalDevices: (state) => state.devices.filter(d => d.status === 'CRITICAL'),
    warningDevices: (state) => state.devices.filter(d => d.status === 'WARNING'),
    healthyDevices: (state) => state.devices.filter(d => d.status === 'HEALTHY'),
    latestIncident: (state) => state.latestIncidents?.[0] || null,

    overallHealth: (state) => {
      if (state.openIncidents > 0) return 'CRITICAL'
      if (state.devices.some(d => d.status === 'WARNING')) return 'WARNING'
      return 'HEALTHY'
    },
  },

  actions: {
    async fetchStatus() {
      try {
        this.loading = true
        const response = await api.getStatus()
        const data = response.data

        this.devices = data.devices || []
        this.deviceCount = data.devices?.length || 0
        this.openIncidents = data.open_incidents || 0
        this.healedToday = data.healed_today || 0
        this.totalIncidents = data.incident_count || 0
        this.latestIncidents = data.latest_incidents || []
        this.recentHealings = data.recent_healings || []
        this.lastUpdated = new Date()
        this.error = null
      } catch (err) {
        this.error = 'Failed to fetch status: ' + err.message
        console.error(this.error, err)
      } finally {
        this.loading = false
      }
    },

    async fetchTelemetry() {
      try {
        this.telemetryError = null
        const response = await api.getTelemetry()
        const telemetryData = response.data.telemetry || []
        
        // Extract all records and group by timestamp to compute single average per timestamp
        const timestampMap = new Map()
        
        if (Array.isArray(telemetryData)) {
          telemetryData.forEach(deviceGroup => {
            if (deviceGroup.records && Array.isArray(deviceGroup.records)) {
              deviceGroup.records.forEach(record => {
                const key = record.timestamp
                if (!timestampMap.has(key)) {
                  timestampMap.set(key, [])
                }
                timestampMap.get(key).push({
                  cpu_usage: parseFloat(record.cpu) || 0,
                  memory_usage: parseFloat(record.memory) || 0,
                  packet_loss: parseFloat(record.packet_loss) || 0,
                  device: deviceGroup.device,
                })
              })
            }
          })
        }
        
        // Convert map to array of averaged telemetry points
        const avgPoints = Array.from(timestampMap.entries())
          .map(([timestamp, records]) => {
            const count = records.length
            const cpu = records.reduce((sum, r) => sum + r.cpu_usage, 0) / count
            const memory = records.reduce((sum, r) => sum + r.memory_usage, 0) / count
            const packet_loss = records.reduce((sum, r) => sum + r.packet_loss, 0) / count
            
            return {
              timestamp,
              cpu_usage: Math.min(100, Math.max(0, cpu)),
              memory_usage: Math.min(100, Math.max(0, memory)),
              packet_loss: Math.min(100, Math.max(0, packet_loss)),
            }
          })
          .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
        
        // Keep only the last 30 unique timestamps
        if (avgPoints.length > 0) {
          this.telemetryHistory = avgPoints.slice(-30)
          console.log('Telemetry updated:', this.telemetryHistory.length, 'points')
        }
      } catch (err) {
        this.telemetryError = 'Failed to load telemetry.'
        console.error('Failed to fetch telemetry:', err)
      }
    },

    async fetchRLStats() {
      try {
        this.rlError = null
        const response = await api.getRLStats()
        this.rlStats = response.data
      } catch (err) {
        this.rlStats = null
        this.rlError = 'Failed to load RL stats.'
        throw new Error('Failed to fetch RL stats: ' + err.message)
      }
    },

    async fetchXaiExplanation(incidentId, force = false) {
      if (!incidentId) return
      if (!force && incidentId === this.activeXaiIncidentId && this.xaiExplanation) return

      this.xaiLoading = true
      this.xaiError = null

      try {
        const response = await api.getDiagnosisExplanation(incidentId)
        this.xaiExplanation = response.data || null
        this.activeXaiIncidentId = incidentId
      } catch (err) {
        this.xaiExplanation = null
        this.xaiError = 'Unable to load diagnosis explanation.'
        console.error('Failed to fetch XAI explanation:', err)
      } finally {
        this.xaiLoading = false
      }
    },
    async approveHealing(id) {
      await api.approveHealing(id)
      await this.fetchStatus()
    },

    async rejectHealing(id) {
      await api.rejectHealing(id)
      await this.fetchStatus()
    },

    async approveIncident(id) {
      return this.approveHealing(id)
    },

    async rejectIncident(id) {
      return this.rejectHealing(id)
    },

    async checkAuth() {
      try {
        const response = await api.authStatus()
        const data = response.data

        this.authenticated = Boolean(data.authenticated)
        this.username = data.username || null
        this.isAdmin = Boolean(data.is_admin)
        this.authError = null
      } catch (err) {
        this.authenticated = false
        this.username = null
        this.isAdmin = false
        this.authError = 'Unable to verify authentication.'
        console.error('Auth status failed:', err)
      }
    },

    async login(username, password) {
      this.authenticating = true
      this.authError = null
      try {
        const response = await api.login({ username, password })
        const data = response.data
        this.authenticated = Boolean(data.authenticated)
        this.username = data.username || null
        this.isAdmin = Boolean(data.is_admin)
        return this.authenticated
      } catch (err) {
        this.authError = err.response?.data?.error || 'Login failed. Check credentials.'
        this.authenticated = false
        this.username = null
        this.isAdmin = false
        return false
      } finally {
        this.authenticating = false
      }
    },

    async logout() {
      try {
        await api.logout()
      } catch (err) {
        console.warn('Logout failed:', err)
      } finally {
        this.authenticated = false
        this.username = null
        this.isAdmin = false
      }
    },

    async startAutoRefresh(intervalMs = 2000) {
      this.stopAutoRefresh()
      await this.fetchStatus()
      await this.fetchTelemetry()
      if (this.latestIncident?.id) {
        await this.fetchXaiExplanation(this.latestIncident.id)
      }

      this.refreshInterval = setInterval(async () => {
        await this.fetchStatus()
        await this.fetchTelemetry()
        if (this.latestIncident?.id) {
          await this.fetchXaiExplanation(this.latestIncident.id)
        }
      }, intervalMs)
    },

    stopAutoRefresh() {
      if (this.refreshInterval) {
        clearInterval(this.refreshInterval)
        this.refreshInterval = null
      }
    },
  },
})