<template>
  <v-card class="telemetry-card rounded-xl pa-2" elevation="0">
    <v-card-title class="d-flex align-center py-3 px-4">
      <div class="d-flex align-center">
        <v-avatar color="cyan-accent-4" variant="tonal" size="36" class="mr-3">
          <v-icon icon="mdi-chart-timeline-variant" size="20" />
        </v-avatar>
        <div>
          <div class="d-flex align-center ga-2">
            <span class="text-h6 font-weight-bold text-slate-100">Real-Time Telemetry</span>
            <v-chip size="x-small" color="success" variant="flat" class="live-pulse-chip font-weight-bold">
              LIVE
            </v-chip>
          </div>
          <p class="text-caption text-slate-400 mb-0 font-weight-regular">
            System-wide averages — rolling 30-point window (refreshed every 2 seconds)
          </p>
        </div>
      </div>
    </v-card-title>

    <v-card-text class="pt-2 pb-4">
      <div v-if="store.telemetryError" class="state-panel text-center py-10">
        <v-icon icon="mdi-alert-circle-outline" size="48" color="error" class="mb-4" />
        <p class="text-body-1 text-error mb-2">{{ store.telemetryError }}</p>
        <v-btn
          variant="outlined"
          color="cyan-accent-2"
          prepend-icon="mdi-refresh"
          :loading="retrying"
          @click="retryTelemetry"
        >
          Retry
        </v-btn>
      </div>

      <div v-else-if="isInitialLoading" class="chart-container">
        <v-skeleton-loader type="image" height="100%" class="rounded-lg" />
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

// Canvas Soft Gradient Generator (15% opacity fading to 0%)
function createGradient(ctx, colorHex) {
  const gradient = ctx.createLinearGradient(0, 0, 0, 320)
  gradient.addColorStop(0, `${colorHex}26`) // ~15% opacity at top
  gradient.addColorStop(1, `${colorHex}00`) // 0% opacity (transparent) at bottom
  return gradient
}

const chartData = computed(() => {
  const points = store.telemetryHistory.slice(-30)
  const chartInstance = chartRef.value?.chart

  let cpuBg = 'rgba(0, 229, 255, 0.05)'
  let memBg = 'rgba(224, 64, 251, 0.05)'
  let lossBg = 'rgba(255, 82, 82, 0.05)'

  if (chartInstance && chartInstance.ctx) {
    const ctx = chartInstance.ctx
    cpuBg = createGradient(ctx, COLORS.cpu)
    memBg = createGradient(ctx, COLORS.memory)
    lossBg = createGradient(ctx, COLORS.packetLoss)
  }

  return {
    labels: formatLabels(points),
    datasets: [
      {
        label: 'CPU Usage (%)',
        data: points.map(p => p.cpu_usage ?? 0),
        borderColor: COLORS.cpu,
        backgroundColor: cpuBg,
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 6,
        borderWidth: 2.5,
      },
      {
        label: 'Memory Usage (%)',
        data: points.map(p => p.memory_usage ?? 0),
        borderColor: COLORS.memory,
        backgroundColor: memBg,
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 6,
        borderWidth: 2.5,
      },
      {
        label: 'Packet Loss (%)',
        data: points.map(p => p.packet_loss ?? 0),
        borderColor: COLORS.packetLoss,
        backgroundColor: lossBg,
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 6,
        borderWidth: 2.5,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 400, easing: 'easeOutQuart' },
  interaction: { intersect: false, mode: 'index' },
  plugins: {
    legend: {
      position: 'top',
      align: 'end',
      labels: {
        color: '#94a3b8',
        usePointStyle: true,
        pointStyle: 'circle',
        padding: 20,
        font: { size: 12, weight: '600' },
      },
    },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      titleColor: '#f8fafc',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(0, 229, 255, 0.2)',
      borderWidth: 1,
      padding: 12,
      cornerRadius: 10,
      callbacks: {
        label(context) {
          const label = context.dataset.label || ''
          const value = context.parsed.y
          return ` ${label}: ${value?.toFixed(1) ?? 0}%`
        },
      },
    },
  },
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      grid: { color: 'rgba(148, 163, 184, 0.06)' },
      ticks: { color: '#64748b', callback: value => `${value}%`, font: { size: 11 } },
    },
    x: {
      grid: { color: 'rgba(148, 163, 184, 0.04)' },
      ticks: { color: '#64748b', maxRotation: 0, autoSkip: true, maxTicksLimit: 10, font: { size: 11 } },
    },
  },
}

watch(
  () => store.telemetryHistory,
  () => {
    const chart = chartRef.value?.chart
    if (chart) chart.update('none')
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
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.chart-container {
  position: relative;
  min-height: 360px;
  height: 360px;
}

.live-pulse-chip {
  letter-spacing: 0.5px;
  font-size: 0.65rem !important;
}

.state-panel {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
</style>