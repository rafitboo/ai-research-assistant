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

        // --- Extract Insights / Hypothesis Generator / Research Gap Finder state ---
        insights: { paperQuery: '', paperSuggestions: [], selectedPaper: null, isRunning: false, error: '', data: null },
        hypothesis: { paperQuery: '', paperSuggestions: [], selectedPaper: null, isRunning: false, error: '', data: null },
        gaps: { paperQuery: '', paperSuggestions: [], selectedPaper: null, isRunning: false, error: '', data: null },

        // --- Starred Items state ---
        starred: { activeCategory: 'insights', data: null, isLoading: false, error: '' },
    
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

        // --- Extract Insights / Hypothesis Generator / Research Gap Finder: shared paper search ---
        async searchPapersInto(toolKey) {
            const s = this[toolKey];
            if (s.paperQuery.trim().length < 2) { s.paperSuggestions = []; return; }
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/journal/autocomplete-papers?q=${encodeURIComponent(s.paperQuery)}`, { headers: this.authHeaders });
                if (res.ok) s.paperSuggestions = await res.json();
            } catch (err) { console.error(err); }
        },
        selectPaperInto(toolKey, paper) {
            const s = this[toolKey];
            s.selectedPaper = paper;
            s.paperQuery = paper.title;
            s.paperSuggestions = [];
        },

        // --- Extract Insights (reuses the existing summary generate/get endpoints) ---
        async runInsights() {
            const s = this.insights;
            if (!s.selectedPaper) return;
            s.isRunning = true; s.error = '';
            try {
                const paperId = s.selectedPaper.id;
                const genRes = await fetch(`http://127.0.0.1:8000/api/ai/summary/${paperId}/generate`, { method: 'POST', headers: this.authHeaders });
                if (!genRes.ok) {
                    const err = await genRes.json().catch(() => ({}));
                    s.error = err.detail || `Request failed (${genRes.status})`;
                    s.isRunning = false;
                    return;
                }
                const res = await fetch(`http://127.0.0.1:8000/api/ai/summary/${paperId}`, { headers: this.authHeaders });
                const json = await res.json();
                if (json.status === 'exists') s.data = json.data.insights;
            } catch (err) { s.error = err.message; console.error(err); }
            s.isRunning = false;
        },

        // --- Hypothesis Generator ---
        async runHypothesis() {
            const s = this.hypothesis;
            if (!s.selectedPaper) return;
            s.isRunning = true; s.error = '';
            try {
                const paperId = s.selectedPaper.id;
                const genRes = await fetch(`http://127.0.0.1:8000/api/ai/hypothesis/${paperId}/generate`, { method: 'POST', headers: this.authHeaders });
                if (!genRes.ok) {
                    const err = await genRes.json().catch(() => ({}));
                    s.error = err.detail || `Request failed (${genRes.status})`;
                    s.isRunning = false;
                    return;
                }
                const res = await fetch(`http://127.0.0.1:8000/api/ai/hypothesis/${paperId}`, { headers: this.authHeaders });
                const json = await res.json();
                if (json.status === 'exists') s.data = json.data;
            } catch (err) { s.error = err.message; console.error(err); }
            s.isRunning = false;
        },

        // --- Research Gap Finder (single-paper) ---
        async runGaps() {
            const s = this.gaps;
            if (!s.selectedPaper) return;
            s.isRunning = true; s.error = '';
            try {
                const paperId = s.selectedPaper.id;
                const genRes = await fetch(`http://127.0.0.1:8000/api/ai/gaps/${paperId}/generate`, { method: 'POST', headers: this.authHeaders });
                if (!genRes.ok) {
                    const err = await genRes.json().catch(() => ({}));
                    s.error = err.detail || `Request failed (${genRes.status})`;
                    s.isRunning = false;
                    return;
                }
                const res = await fetch(`http://127.0.0.1:8000/api/ai/gaps/${paperId}`, { headers: this.authHeaders });
                const json = await res.json();
                if (json.status === 'exists') s.data = json.data;
            } catch (err) { s.error = err.message; console.error(err); }
            s.isRunning = false;
        },

        // --- Starred Items ---
        async fetchStarredItems() {
            this.starred.isLoading = true;
            this.starred.error = '';
            try {
                const res = await fetch('http://127.0.0.1:8000/api/ai/starred', { headers: this.authHeaders });
                if (res.ok) {
                    this.starred.data = await res.json();
                } else {
                    const err = await res.json().catch(() => ({}));
                    this.starred.error = err.detail || `Request failed (${res.status})`;
                }
            } catch (err) {
                this.starred.error = err.message;
                console.error(err);
            }
            this.starred.isLoading = false;
        },
        async unstarItem(categoryKey, item) {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/ai/insights/${item.id}/star`, { method: 'POST', headers: this.authHeaders });
                if (res.ok) {
                    this.starred.data[categoryKey] = this.starred.data[categoryKey].filter(i => i.id !== item.id);
                }
            } catch (err) { console.error(err); }
        },
        async unstarTitle(item) {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/ai/titles/saved/${item.id}`, { method: 'DELETE', headers: this.authHeaders });
                if (res.ok) {
                    this.starred.data.titles = this.starred.data.titles.filter(i => i.id !== item.id);
                }
            } catch (err) { console.error(err); }
        },

        // --- Per-point actions shared by Extract Insights, Hypothesis Generator, Research Gap Finder ---
        async toggleStar(item) {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/ai/insights/${item.id}/star`, { method: 'POST', headers: this.authHeaders });
                if (res.ok) { const json = await res.json(); item.starred = json.starred; }
            } catch (err) { console.error(err); }
        },
        startEdit(item) { item._editing = true; item._editBuffer = item.content; },
        cancelEdit(item) { item._editing = false; },
        async saveEdit(item) {
            if (!item._editBuffer || !item._editBuffer.trim()) return;
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/ai/insights/${item.id}`, {
                    method: 'PUT', headers: this.authHeaders, body: JSON.stringify({ content: item._editBuffer })
                });
                if (res.ok) { item.content = item._editBuffer; item._editing = false; }
            } catch (err) { console.error(err); }
        },
        async regeneratePoint(item) {
            item._regenerating = true;
            item._regenError = '';
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/ai/insights/${item.id}/regenerate`, { method: 'POST', headers: this.authHeaders });
                if (res.ok) {
                    const json = await res.json();
                    item.content = json.content;
                } else {
                    const err = await res.json().catch(() => ({}));
                    item._regenError = err.detail || `Request failed (${res.status})`;
                    console.error('Regenerate failed:', item._regenError);
                }
            } catch (err) {
                item._regenError = err.message;
                console.error(err);
            }
            item._regenerating = false;
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
