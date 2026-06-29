<template>
  <v-card color="surface" elevation="2">
    <v-card-title>
      <v-icon icon="mdi-chart-line" class="mr-2 text-info"></v-icon>
      Real-Time Telemetry
    </v-card-title>

    <v-card-subtitle class="text-secondary">
      System‑wide averages (updated every 2 seconds)
    </v-card-subtitle>

    <v-card-text>
      <!-- Error state -->
      <div v-if="store.telemetryError" class="text-center py-8">
        <v-icon icon="mdi-alert-circle" size="40" color="error" class="mb-3"></v-icon>
        <div class="text-body-2 text-error mb-4">{{ store.telemetryError }}</div>
        <v-btn size="small" variant="outlined" @click="retryTelemetry">
          Retry
        </v-btn>
      </div>

      <!-- Loading state -->
      <div v-else-if="store.telemetryHistory.length === 0" class="text-center py-20">
        <v-progress-circular indeterminate color="primary" size="48" class="mb-4"></v-progress-circular>
        <div class="text-body-2 text-secondary">Collecting telemetry data…</div>
      </div>

      <!-- Chart -->
      <div v-else class="chart-container">
        <Line :data="chartData" :options="chartOptions" :plugins="[shadowPlugin]" />
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
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
  Filler
)

const store = useNetworkStore()
const MAX_POINTS = 30

function formatTelemetryLabels(telemetryHistory) {
  return telemetryHistory.map(point => {
    try {
      const date = new Date(point.timestamp)
      return date.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch (e) {
      return '--:--:--'
    }
  })
}

async function retryTelemetry() {
  try {
    await store.fetchTelemetry()
    console.log('Telemetry retry - fetched', store.telemetryHistory.length, 'points')
  } catch (error) {
    console.error('Retry failed:', error)
  }
}

const chartData = computed(() => {
  const points = store.telemetryHistory || []
  
  if (points.length === 0) {
    return {
      labels: [],
      datasets: [
        { label: 'CPU Usage (%)', data: [], borderColor: '#2CB5E6' },
        { label: 'Memory Usage (%)', data: [], borderColor: '#103B78' },
        { label: 'Packet Loss (%)', data: [], borderColor: '#FF5252' },
      ],
    }
  }

  return {
    labels: formatTelemetryLabels(points),
    datasets: [
      {
        label: 'CPU Usage (%)',
        data: points.map(p => p.cpu_usage || 0),
        borderColor: '#2CB5E6',
        backgroundColor: 'rgba(44, 181, 230, 0.1)',
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 6,
        borderWidth: 3,
        segment: {
          borderColor: ctx => '#2CB5E6',
        },
      },
      {
        label: 'Memory Usage (%)',
        data: points.map(p => p.memory_usage || 0),
        borderColor: '#103B78',
        backgroundColor: 'rgba(16, 59, 120, 0.1)',
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 6,
        borderWidth: 3,
        segment: {
          borderColor: ctx => '#103B78',
        },
      },
      {
        label: 'Packet Loss (%)',
        data: points.map(p => p.packet_loss || 0),
        borderColor: '#FF5252',
        backgroundColor: 'rgba(255, 82, 82, 0.1)',
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 6,
        borderWidth: 3,
        segment: {
          borderColor: ctx => '#FF5252',
        },
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
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
        padding: 20,
        font: {
          size: 13,
          weight: '500',
        },
      },
    },
    tooltip: {
      backgroundColor: '#0f172a',
      titleColor: '#f1f5f9',
      bodyColor: '#cbd5e1',
      borderColor: '#334155',
      borderWidth: 1,
      padding: 12,
      displayColors: true,
      boxPadding: 8,
      titleFont: {
        size: 13,
        weight: 'bold',
      },
      bodyFont: {
        size: 12,
      },
      callbacks: {
        label: function(context) {
          let label = context.dataset.label || ''
          if (label) {
            label += ': '
          }
          if (context.parsed.y !== null) {
            label += context.parsed.y.toFixed(1) + '%'
          }
          return label
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
        drawBorder: true,
      },
      ticks: {
        color: '#94a3b8',
        font: {
          size: 12,
        },
        callback: function(value) {
          return value + '%'
        },
      },
    },
    x: {
      grid: {
        color: 'rgba(148, 163, 184, 0.08)',
        drawBorder: false,
      },
      ticks: {
        color: '#94a3b8',
        font: {
          size: 12,
        },
      },
    },
  },
}

const shadowPlugin = {
  id: 'shadowPlugin',
  afterDraw(chart) {
    const ctx = chart.ctx
    ctx.save()
    ctx.fillStyle = 'rgba(15, 23, 42, 0.15)'
    ctx.fillRect(0, 0, chart.width, chart.height)
    ctx.restore()
  },
}
</script>

<style scoped>
.chart-container {
  position: relative;
  min-height: 400px;
}
</style>