document.addEventListener('alpine:init', () => {
    Alpine.data('summaryApp', (paperId, token) => ({
        paperId: paperId,
        authToken: token,
        status: 'loading',
        isGenerating: false,
        summary: { abstract: '', methodology: '', findings: '' },
        insights: { contribution: [], advantage: [], limitation: [], future_work: [] },
        editingId: null,
        editBuffer: '',
        apiBaseUrl: 'http://127.0.0.1:8000/api/ai/summary',
        get authHeaders() { return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.authToken}` }; },
        init() { this.fetchData(); },
        async fetchData() {
            try {
                const res = await fetch(`${this.apiBaseUrl}/${this.paperId}`, { headers: this.authHeaders });
                const json = await res.json();
                this.status = json.status;
                if (this.status === 'exists') {
                    this.summary = json.data;
                    this.insights = json.data.insights;
                }
            } catch (err) { console.error(err); }
        },
        async generateSummary() {
            this.isGenerating = true;
            try {
                const res = await fetch(`${this.apiBaseUrl}/${this.paperId}/generate`, { method: 'POST', headers: this.authHeaders });
                if (res.ok) await this.fetchData();
            } catch (err) { console.error(err); }
            this.isGenerating = false;
        },
        startEdit(insight) { this.editingId = insight.id; this.editBuffer = insight.content; },
        async saveEdit(insight) {
            if (!this.editBuffer.trim()) return;
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/ai/insights/${insight.id}`, {
                    method: 'PUT', headers: this.authHeaders, body: JSON.stringify({ content: this.editBuffer })
                });
                if (res.ok) { insight.content = this.editBuffer; this.editingId = null; }
            } catch (err) { console.error(err); }
        }
    }));
});