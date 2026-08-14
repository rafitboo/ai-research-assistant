document.addEventListener('alpine:init', () => {
    Alpine.data('assistantApp', (token) => ({
        authToken: token,
        activeTool: 'summarize',

        // --- Summarize Paper state ---
        paperQuery: '',
        paperSuggestions: [],
        selectedPaper: null,
        isSummarizing: false,
        summaryResult: null,
        summaryError: '',


        // --- Title Generator state ---
        topicInput: '',
        isGeneratingTitles: false,
        generatedTitles: [],
        savedTitles: [],
        titlesError: '',

        get authHeaders() {
            return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.authToken}` };
        },

        init() {
            const params = new URLSearchParams(window.location.search);
            const tool = params.get('tool');
            if (tool) this.activeTool = tool;

            const paperId = params.get('paper_id');
            const paperTitle = params.get('paper_title');
            if (paperId) {
                this.selectedPaper = { id: paperId, title: paperTitle || '' };
                this.paperQuery = paperTitle || '';
            }

            this.fetchSavedTitles();
        },

        // --- Summarize Paper (reuses journal.py autocomplete + ai_features.py summary endpoints) ---
        async searchPapers() {
            if (this.paperQuery.trim().length < 2) { this.paperSuggestions = []; return; }
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/journal/autocomplete-papers?q=${encodeURIComponent(this.paperQuery)}`, { headers: this.authHeaders });
                if (res.ok) this.paperSuggestions = await res.json();
            } catch (err) { console.error(err); }
        },
        selectPaper(paper) {
            this.selectedPaper = paper;
            this.paperQuery = paper.title;
            this.paperSuggestions = [];
        },
        async runSummarize() {
            if (!this.selectedPaper) return;
            this.isSummarizing = true;
            this.summaryError = '';
            try {
                const paperId = this.selectedPaper.id;
                const genRes = await fetch(`http://127.0.0.1:8000/api/ai/summary/${paperId}/generate`, { method: 'POST', headers: this.authHeaders });
                if (!genRes.ok) {
                    const err = await genRes.json().catch(() => ({}));
                    this.summaryError = err.detail || `Request failed (${genRes.status})`;
                    console.error('Summarize failed:', this.summaryError);
                    this.isSummarizing = false;
                    return;
                }
                const res = await fetch(`http://127.0.0.1:8000/api/ai/summary/${paperId}`, { headers: this.authHeaders });
                const json = await res.json();
                if (json.status === 'exists') this.summaryResult = json.data;
            } catch (err) {
                this.summaryError = err.message;
                console.error(err);
            }
            this.isSummarizing = false;
        },

        // --- Title Generator (reuses ai_features.py title endpoints, same as ai_titles.js) ---
        async runTitles() {
            this.isGeneratingTitles = true;
            this.titlesError = '';
            try {
                const res = await fetch('http://127.0.0.1:8000/api/ai/titles/generate', {
                    method: 'POST', headers: this.authHeaders, body: JSON.stringify({ topic: this.topicInput })
                });
                if (res.ok) {
                    this.generatedTitles = await res.json();
                } else {
                    const err = await res.json().catch(() => ({}));
                    this.titlesError = err.detail || `Request failed (${res.status})`;
                    console.error('Title generation failed:', this.titlesError);
                }
            } catch (err) {
                this.titlesError = err.message;
                console.error(err);
            }
            this.isGeneratingTitles = false;
        },
        
        async saveTitle(titleText) {
            try {
                const res = await fetch('http://127.0.0.1:8000/api/ai/titles/save', {
                    method: 'POST', headers: this.authHeaders, body: JSON.stringify({ title_text: titleText })
                });
                if (res.ok) { await this.fetchSavedTitles(); }
            } catch (err) { console.error(err); }
        },
        async fetchSavedTitles() {
            try {
                const res = await fetch('http://127.0.0.1:8000/api/ai/titles/saved', { headers: this.authHeaders });
                if (res.ok) this.savedTitles = await res.json();
            } catch (err) { console.error(err); }
        },

        // --- Shared ---
        copySuccess: '',

        async copyJSON(data) {
            if (!data) return;

            try {
                await navigator.clipboard.writeText(JSON.stringify(data, null, 2));

                this.copySuccess = 'Copied!';

                setTimeout(() => {
                    this.copySuccess = '';
                }, 2000);

            } catch (err) {
                console.error('Copy failed:', err);
                this.copySuccess = 'Copy failed';

                setTimeout(() => {
                    this.copySuccess = '';
                }, 2000);
            }
        }
    }));
});
