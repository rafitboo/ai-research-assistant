document.addEventListener('alpine:init', () => {
    Alpine.data('libraryAnalytics', () => ({
        isLoading: true,
        selectedDays: null, // null represents All Time
        stats: {
            total: 0,
            avg_completion: 0,
            status_breakdown: {},
            top_areas: [],
            streak: 0,
            activity_timeline: [],
            project_snapshots: []
        },
        chartInstances: [],

        get headers() {
            return {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${window.USER_TOKEN}`
            };
        },

        async init() {
            await this.fetchAnalytics();
        },

        async setTimeRange(days) {
            this.selectedDays = days;
            await this.fetchAnalytics();
        },

        async fetchAnalytics() {
            this.isLoading = true;
            try {
                let url = `/api/analytics/dashboard`;
                if (this.selectedDays !== null) {
                    url += `?days=${this.selectedDays}`;
                }

                const res = await fetch(url, { headers: this.headers });
                if (res.ok) {
                    this.stats = await res.json();
                    if (this.stats.total > 0) {
                        setTimeout(() => this.renderCharts(), 100);
                    }
                }
            } catch (err) {
                console.error("Failed to load analytics dashboard:", err);
            } finally {
                this.isLoading = false;
            }
        },

        renderCharts() {
            // Clean up existing charts to avoid layout bugs on re-filter
            this.chartInstances.forEach(chart => chart.destroy());
            this.chartInstances = [];

            // 1. Reading Activity Line Chart
            const activityCtx = document.getElementById('activityChart');
            if (activityCtx && this.stats.activity_timeline.length > 0) {
                const activityChart = new Chart(activityCtx, {
                    type: 'line',
                    data: {
                        labels: this.stats.activity_timeline.map(a => a.date),
                        datasets: [{
                            label: 'Papers Added / Read',
                            data: this.stats.activity_timeline.map(a => a.count),
                            borderColor: '#5B3DF5',
                            backgroundColor: 'rgba(91, 61, 245, 0.1)',
                            fill: true,
                            tension: 0.3,
                            borderWidth: 3
                        }]
                    },
                    options: { 
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                    }
                });
                this.chartInstances.push(activityChart);
            }

            // 2. Status Doughnut Chart
            const statusCtx = document.getElementById('statusChart');
            if (statusCtx && Object.keys(this.stats.status_breakdown).length > 0) {
                const statusChart = new Chart(statusCtx, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(this.stats.status_breakdown),
                        datasets: [{
                            data: Object.values(this.stats.status_breakdown),
                            backgroundColor: ['#10B981', '#6366F1', '#94A3B8'], // Emerald, Indigo, Slate
                            borderWidth: 0,
                            hoverOffset: 4
                        }]
                    },
                    options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
                });
                this.chartInstances.push(statusChart);
            }

            // 3. Areas Bar Chart
            const areasCtx = document.getElementById('areasChart');
            if (areasCtx && this.stats.top_areas.length > 0) {
                const areasChart = new Chart(areasCtx, {
                    type: 'bar',
                    data: {
                        labels: this.stats.top_areas.map(a => a.area),
                        datasets: [{
                            label: 'Papers',
                            data: this.stats.top_areas.map(a => a.count),
                            backgroundColor: '#5B3DF5',
                            borderRadius: 6
                        }]
                    },
                    options: { 
                        maintainAspectRatio: false, 
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                    }
                });
                this.chartInstances.push(areasChart);
            }
        }
    }));
});