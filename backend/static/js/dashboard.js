const { createApp } = Vue;

createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            stats: {
                devices: [],
                incident_count: 0,
                open_incidents: 0,
                healed_today: 0,
                latest_incidents: [],
                recent_healings: [],
            },
            telemetry: {},
            analytics: {
                mttr: 0,
                healing_success_rate: 0,
                avg_detection_time: 0,
            },
            loadedAt: null,
            activeIncidentId: null,
            activeDeviceId: null,
            selectedDeviceForChart: null,
            xai: {
                title: 'Explainable AI (XAI)',
                lines: ['NeuroSynapse is monitoring your network. Click an incident to see details.'],
            },
            error: null,
            refreshing: false,
            activeTab: 'overview',
            searchQuery: '',
            filterIncidentType: '',
            filterSeverity: '',
            filterTimeRange: 7,
            chartData: null,
            chartInstance: null,
        };
    },
    computed: {
        deviceCount() {
            return this.stats.devices.length;
        },
        statusClass() {
            return this.stats.open_incidents > 0 ? 'status-badge status-critical' : 'status-badge status-healthy';
        },
        statusText() {
            return this.stats.open_incidents > 0 ? '● INCIDENT ACTIVE' : '● SYSTEM HEALTHY';
        },
        refreshText() {
            return this.loadedAt ? `Last updated: ${this.loadedAt.toLocaleTimeString()}` : 'Last updated: --';
        },
        selectedIncident() {
            return this.stats.latest_incidents.find(i => i.id === this.activeIncidentId) || null;
        },
        selectedDevice() {
            return this.stats.devices.find(d => d.id === this.selectedDeviceForChart) || null;
        },
        currentlyRefreshing() {
            return this.refreshing ? 'Refreshing...' : '';
        },
        filteredIncidents() {
            return this.stats.latest_incidents.filter(i => {
                const matchesSearch = !this.searchQuery || 
                    i.device.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
                    i.type.toLowerCase().includes(this.searchQuery.toLowerCase());
                const matchesType = !this.filterIncidentType || i.type === this.filterIncidentType;
                return matchesSearch && matchesType;
            });
        },
        incidentTypes() {
            return [...new Set(this.stats.latest_incidents.map(i => i.type))];
        },
    },
    methods: {
        async fetchStatus() {
            this.refreshing = true;
            try {
                const response = await fetch('/api/status/');
                if (!response.ok) throw new Error(`Status fetch failed: ${response.status}`);
                const data = await response.json();
                this.stats = data;
                this.loadedAt = new Date();
                this.error = null;
                if (this.activeIncidentId) {
                    const found = this.stats.latest_incidents.find(i => i.id === this.activeIncidentId);
                    if (!found) this.activeIncidentId = null;
                }
            } catch (err) {
                console.error(err);
                this.error = 'Unable to refresh status. Check backend connectivity.';
            } finally {
                this.refreshing = false;
            }
        },
        async fetchTelemetry() {
            try {
                const response = await fetch('/api/telemetry/');
                if (!response.ok) throw new Error('Telemetry fetch failed');
                const data = await response.json();
                this.telemetry = data.telemetry.reduce((acc, t) => {
                    acc[t.device] = t.records;
                    return acc;
                }, {});
                if (this.selectedDeviceForChart && this.selectedDevice) {
                    this.updateChart();
                }
            } catch (err) {
                console.error('Telemetry fetch error:', err);
            }
        },
        async fetchAnalytics() {
            try {
                const response = await fetch('/api/analytics/');
                if (!response.ok) throw new Error('Analytics fetch failed');
                const data = await response.json();
                this.analytics = data;
            } catch (err) {
                console.error('Analytics fetch error:', err);
            }
        },
        formatValue(value) {
            return value == null ? '--' : value;
        },
        formatPercent(value) {
            return value == null ? '--' : `${value.toFixed(1)}%`;
        },
        formatDate(timestamp) {
            return timestamp ? new Date(timestamp).toLocaleString() : '--';
        },
        formatDateShort(timestamp) {
            return timestamp ? new Date(timestamp).toLocaleTimeString() : '--';
        },
        statusDotClass(status) {
            if (status === 'HEALTHY') return 'dot-healthy';
            if (status === 'WARNING') return 'dot-warning';
            if (status === 'CRITICAL') return 'dot-critical';
            return 'dot-unknown';
        },
        badgeClass(type) {
            const normalized = type.toLowerCase().replace(/\s+/g, '_');
            return `badge badge-${normalized}`;
        },
        severityBadgeClass(incident) {
            if (incident.confidence > 0.8) return 'badge-severity-critical';
            if (incident.confidence > 0.5) return 'badge-severity-warning';
            return 'badge-severity-info';
        },
        async selectIncident(incident) {
            this.activeIncidentId = incident.id;
            await this.fetchDiagnosis(incident.id);
        },
        async fetchDiagnosis(incidentId) {
            this.xai.title = `Loading explanation for incident #${incidentId}...`;
            this.xai.lines = ['Requesting diagnosis from the XAI engine.'];
            try {
                const response = await fetch(`/api/xai/diagnosis/${incidentId}/`);
                const explanation = await response.json();
                if (!response.ok) throw new Error(explanation.error || 'XAI endpoint error');
                this.xai.title = `Diagnosis for Incident #${incidentId}`;
                this.xai.lines = [
                    `Device: ${explanation.device}`,
                    `Status: ${explanation.status}`,
                    `Detected: ${this.formatDate(explanation.detected_at)}`,
                    `Failure Type: ${explanation.failure_type || 'N/A'}`,
                    `Confidence: ${explanation.confidence != null ? `${(explanation.confidence * 100).toFixed(1)}%` : 'N/A'}`,
                    explanation.summary || 'No explanation available.',
                ];
            } catch (err) {
                console.error(err);
                this.xai.title = 'XAI explanation unavailable';
                this.xai.lines = ['Unable to load explanation from backend.'];
            }
        },
        selectDevice(device) {
            this.selectedDeviceForChart = device.id;
            this.$nextTick(() => {
                this.updateChart();
            });
        },
        updateChart() {
            if (!this.selectedDevice || !this.telemetry[this.selectedDevice.name]) {
                return;
            }
            const records = this.telemetry[this.selectedDevice.name];
            const reversedRecords = [...records].reverse();
            
            const labels = reversedRecords.map(r => new Date(r.timestamp).toLocaleTimeString());
            const cpuData = reversedRecords.map(r => r.cpu || 0);
            const memData = reversedRecords.map(r => r.memory || 0);
            const lossData = reversedRecords.map(r => r.packet_loss || 0);

            const ctx = document.getElementById('telemetry-chart');
            if (!ctx) return;

            if (this.chartInstance) {
                this.chartInstance.destroy();
            }

            this.chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'CPU Usage (%)',
                            data: cpuData,
                            borderColor: '#38bdf8',
                            backgroundColor: 'rgba(56, 189, 248, 0.1)',
                            tension: 0.3,
                            borderWidth: 2,
                        },
                        {
                            label: 'Memory Usage (%)',
                            data: memData,
                            borderColor: '#f59e0b',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            tension: 0.3,
                            borderWidth: 2,
                        },
                        {
                            label: 'Packet Loss (%)',
                            data: lossData,
                            borderColor: '#ef4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            tension: 0.3,
                            borderWidth: 2,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            labels: { color: '#94a3b8' },
                        },
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' },
                        },
                        x: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' },
                        },
                    },
                },
            });
        },
        switchTab(tab) {
            this.activeTab = tab;
            if (tab === 'telemetry' && this.selectedDevice && !this.chartInstance) {
                this.$nextTick(() => {
                    this.updateChart();
                });
            }
        },
    },
    mounted() {
        this.fetchStatus();
        this.fetchTelemetry();
        this.fetchAnalytics();
        this.interval = setInterval(() => {
            this.fetchStatus();
            this.fetchTelemetry();
        }, 5000);
        this.analyticsInterval = setInterval(this.fetchAnalytics, 30000);
    },
    unmounted() {
        clearInterval(this.interval);
        clearInterval(this.analyticsInterval);
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }
    },
}).mount('#dashboard-app');
