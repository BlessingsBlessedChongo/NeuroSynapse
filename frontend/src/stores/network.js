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

    // Telemetry history
    telemetryHistory: [],

    // Refresh interval
    refreshInterval: null,
  }),

  getters: {
    criticalDevices: (state) => state.devices.filter(d => d.status === 'CRITICAL'),
    warningDevices: (state) => state.devices.filter(d => d.status === 'WARNING'),
    healthyDevices: (state) => state.devices.filter(d => d.status === 'HEALTHY'),

    overallHealth: (state) => {
      if (state.openIncidents > 0) return 'CRITICAL'
      if (state.devices.some(d => d.status === 'WARNING')) return 'WARNING'
      return 'HEALTHY'
    },
  },

  actions: {
    async fetchStatus() {
      try {
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
        console.error(this.error)
      }
    },

    async fetchTelemetry() {
      try {
        const response = await api.getTelemetry()
        this.telemetryHistory = response.data.telemetry || []
      } catch (err) {
        console.error('Failed to fetch telemetry:', err)
      }
    },

    async fetchRLStats() {
      try {
        const response = await api.getRLStats()
        this.rlStats = response.data
      } catch (err) {
        console.error('Failed to fetch RL stats:', err)
      }
    },

    startAutoRefresh(intervalMs = 2000) {
      this.stopAutoRefresh()
      this.fetchStatus()
      this.refreshInterval = setInterval(() => {
        this.fetchStatus()
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