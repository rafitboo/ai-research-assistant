document.addEventListener('alpine:init', () => {
    Alpine.data('titleGenApp', (token) => ({
        authToken: token,
        topicInput: '',
        isGenerating: false,
        generatedTitles: [],
        savedTitles: [],
        apiBaseUrl: 'http://127.0.0.1:8000/api/ai/titles',
        get authHeaders() { return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.authToken}` }; },
        init() { this.fetchSavedTitles(); },
        async generateTitles() {
            this.isGenerating = true;
            try {
                const res = await fetch(`${this.apiBaseUrl}/generate`, {
                    method: 'POST', headers: this.authHeaders, body: JSON.stringify({ topic: this.topicInput })
                });
                if (res.ok) { this.generatedTitles = await res.json(); }
            } catch (err) { console.error(err); }
            this.isGenerating = false;
        },
        async saveTitle(titleText) {
            try {
                const res = await fetch(`${this.apiBaseUrl}/save`, {
                    method: 'POST', headers: this.authHeaders, body: JSON.stringify({ title_text: titleText })
                });
                if (res.ok) { await this.fetchSavedTitles(); alert("Title saved successfully!"); }
            } catch (err) { console.error(err); }
        },
        async fetchSavedTitles() {
            try {
                const res = await fetch(`${this.apiBaseUrl}/saved`, { headers: this.authHeaders });
                if (res.ok) { this.savedTitles = await res.json(); }
            } catch (err) { console.error(err); }
        }
    }));
});