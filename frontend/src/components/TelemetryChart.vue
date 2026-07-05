<template>
  <v-card color="surface" elevation="2" class="telemetry-card">
    <v-card-title class="d-flex align-center">
      <v-icon icon="mdi-chart-line" class="mr-2 text-info" />
      Real-Time Telemetry
    </v-card-title>

    <v-card-subtitle class="text-medium-emphasis pb-2">
      System-wide averages — rolling 30-point window (refreshed every 2 seconds)
    </v-card-subtitle>

    <v-card-text>
      <div v-if="store.telemetryError" class="state-panel text-center py-10">
        <v-icon icon="mdi-alert-circle-outline" size="48" color="error" class="mb-4" />
        <p class="text-body-1 text-error mb-2">{{ store.telemetryError }}</p>
        <v-btn
          variant="outlined"
          color="primary"
          prepend-icon="mdi-refresh"
          :loading="retrying"
          @click="retryTelemetry"
        >
          Retry
        </v-btn>
      </div>

      <div v-else-if="isInitialLoading" class="state-panel text-center py-10">
        <v-progress-circular indeterminate color="primary" size="52" width="4" class="mb-4" />
        <p class="text-body-2 text-medium-emphasis">Collecting telemetry data…</p>
      </div>

      <div v-else class="chart-container">
        <Line
          ref="chartRef"
          :data="chartData"
          :options="chartOptions"
        />
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { useNetworkStore } from '@/stores/network'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
)

const store = useNetworkStore()
const chartRef = ref(null)
const retrying = ref(false)

const COLORS = {
  cpu: '#00E5FF',
  memory: '#E040FB',
  packetLoss: '#FF5252',
}

const isInitialLoading = computed(
  () => !store.telemetryError && store.telemetryHistory.length === 0,
)

function formatLabels(history) {
  return history.map(point => {
    try {
      return new Date(point.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch {
      return '--:--:--'
    }
  })
}

const chartData = computed(() => {
  const points = store.telemetryHistory.slice(-30)

  return {
    labels: formatLabels(points),
    datasets: [
      {
        label: 'CPU Usage (%)',
        data: points.map(p => p.cpu_usage ?? 0),
        borderColor: COLORS.cpu,
        backgroundColor: 'rgba(0, 229, 255, 0.04)',
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 6,
        borderWidth: 3,
      },
      {
        label: 'Memory Usage (%)',
        data: points.map(p => p.memory_usage ?? 0),
        borderColor: COLORS.memory,
        backgroundColor: 'rgba(224, 64, 251, 0.04)',
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 6,
        borderWidth: 3,
      },
      {
        label: 'Packet Loss (%)',
        data: points.map(p => p.packet_loss ?? 0),
        borderColor: COLORS.packetLoss,
        backgroundColor: 'rgba(255, 82, 82, 0.04)',
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 6,
        borderWidth: 3,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: {
    duration: 600,
    easing: 'easeOutQuart',
  },
  transitions: {
    active: {
      animation: {
        duration: 400,
      },
    },
  },
  interaction: {
    intersect: false,
    mode: 'index',
  },
  plugins: {
    legend: {
      position: 'top',
      labels: {
        color: '#94a3b8',
        usePointStyle: true,
        pointStyle: 'circle',
        padding: 18,
        font: { size: 12, weight: '600' },
      },
    },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      titleColor: '#f1f5f9',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(51, 65, 85, 0.8)',
      borderWidth: 1,
      padding: 12,
      callbacks: {
        label(context) {
          const label = context.dataset.label || ''
          const value = context.parsed.y
          return `${label}: ${value?.toFixed(1) ?? 0}%`
        },
      },
    },
  },
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      grid: {
        color: 'rgba(148, 163, 184, 0.1)',
      },
      ticks: {
        color: '#94a3b8',
        callback: value => `${value}%`,
      },
    },
    x: {
      grid: {
        color: 'rgba(148, 163, 184, 0.06)',
      },
      ticks: {
        color: '#94a3b8',
        maxRotation: 0,
        autoSkip: true,
        maxTicksLimit: 10,
      },
    },
  },
}

watch(
  () => store.telemetryHistory,
  () => {
    const chart = chartRef.value?.chart
    if (chart) {
      chart.update('none')
    }
  },
  { deep: true },
)

async function retryTelemetry() {
  retrying.value = true
  try {
    await store.fetchTelemetry()
  } finally {
    retrying.value = false
  }
}
</script>

<style scoped>
.telemetry-card {
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.chart-container {
  position: relative;
  min-height: 380px;
  height: 380px;
}

.state-panel {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
</style>
