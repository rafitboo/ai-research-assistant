document.addEventListener('alpine:init', () => {
    Alpine.data('journalApp', (token) => ({
        authToken: token,
        entries: [],
        searchResults: [],
        searchQuery: '',
        selectedPaperTitle: '',
        isSubmitting: false,

        filterCategory: 'All',
        filterTag: null,
        timelineSearch: '',
        editingId: null,

        toast: { show: false, message: '', type: 'success' },

        formData: {
            title: '',
            content: '',
            paper_id: null,
            category: 'General',
            tags: ''
        },

        apiBaseUrl: 'http://127.0.0.1:8000/api/journal',

        get authHeaders() {
            return {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.authToken}`
            };
        },

        init() {
            this.fetchEntries();
            this.$watch('timelineSearch', () => this.debouncedFetch());
            this.$watch('filterCategory', () => this.fetchEntries());
            this.$watch('filterTag', () => this.fetchEntries());
        },

        debouncedFetch() {
            clearTimeout(this._searchTimer);
            this._searchTimer = setTimeout(() => this.fetchEntries(), 300);
        },

        // Entries arrive from the backend already sorted: pinned first, newest to
        // oldest within each group.
        get filteredEntries() {
            return this.entries;
        },

        get allTags() {
            const set = new Set();
            this.entries.forEach(e => {
                (e.tags || '').split(',').map(t => t.trim()).filter(Boolean).forEach(t => set.add(t));
            });
            return Array.from(set);
        },

        showToast(message, type = 'success') {
            this.toast = { show: true, message, type };
            clearTimeout(this._toastTimer);
            this._toastTimer = setTimeout(() => { this.toast.show = false; }, 3000);
        },

        renderMarkdown(rawContent) {
            if (!rawContent) return '';
            return marked.parse(rawContent);
        },

        getCategoryEmoji(category) {
            const map = { 'General': '📝', 'Meeting': '🤝', 'Experiment': '🧪', 'Idea': '💡' };
            return map[category] || '📝';
        },

        async fetchEntries() {
            try {
                const params = new URLSearchParams();
                if (this.timelineSearch) params.set('q', this.timelineSearch);
                if (this.filterCategory && this.filterCategory !== 'All') params.set('category', this.filterCategory);
                if (this.filterTag) params.set('tag', this.filterTag);

                const response = await fetch(`${this.apiBaseUrl}/?${params.toString()}`, { headers: this.authHeaders });
                if (response.ok) {
                    this.entries = await response.json();
                }
            } catch (error) {
                console.error('Network error:', error);
            }
        },

        async searchPapers() {
            if (this.searchQuery.length < 2) {
                this.searchResults = [];
                return;
            }
            try {
                const response = await fetch(`${this.apiBaseUrl}/autocomplete-papers?q=${encodeURIComponent(this.searchQuery)}`, { headers: this.authHeaders });
                if (response.ok) {
                    this.searchResults = await response.json();
                }
            } catch (error) {
                console.error('Search error:', error);
            }
        },

        selectPaper(paper) {
            this.formData.paper_id = paper.id;
            this.selectedPaperTitle = paper.title;
            this.searchQuery = '';
            this.searchResults = [];
        },

        clearSelectedPaper() {
            this.formData.paper_id = null;
            this.selectedPaperTitle = '';
        },

        async submitEntry() {
            this.isSubmitting = true;
            try {
                const isEdit = this.editingId !== null;
                const url = isEdit ? `${this.apiBaseUrl}/${this.editingId}` : `${this.apiBaseUrl}/`;
                const method = isEdit ? 'PUT' : 'POST';

                const response = await fetch(url, {
                    method,
                    headers: this.authHeaders,
                    body: JSON.stringify(this.formData)
                });

                if (response.ok) {
                    await this.fetchEntries(); // re-pull so sort order (pinned, then date) stays correct
                    this.showToast(isEdit ? 'Entry updated' : 'Entry saved');
                    this.resetForm();
                } else {
                    this.showToast('Could not save entry', 'error');
                }
            } catch (error) {
                console.error('Submit error:', error);
                this.showToast('Network error, entry not saved', 'error');
            } finally {
                this.isSubmitting = false;
            }
        },

        resetForm() {
            this.formData = { title: '', content: '', paper_id: null, category: 'General', tags: '' };
            this.editingId = null;
            this.clearSelectedPaper();
        },

        startEdit(entry) {
            this.editingId = entry.id;
            this.formData = {
                title: entry.title || '',
                content: entry.content,
                paper_id: entry.paper_id,
                category: entry.category,
                tags: entry.tags || ''
            };
            if (entry.paper_id) this.selectedPaperTitle = entry.paper_title || '';
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        cancelEdit() {
            this.resetForm();
        },

        async deleteEntry(entryId) {
            if (!confirm('Delete this journal entry? This cannot be undone.')) return;
            try {
                const response = await fetch(`${this.apiBaseUrl}/${entryId}`, {
                    method: 'DELETE',
                    headers: this.authHeaders
                });
                if (response.ok) {
                    this.entries = this.entries.filter(e => e.id !== entryId);
                    this.showToast('Entry deleted');
                } else {
                    this.showToast('Could not delete entry', 'error');
                }
            } catch (error) {
                console.error('Delete error:', error);
                this.showToast('Network error, entry not deleted', 'error');
            }
        },

        async togglePin(entry) {
            try {
                const response = await fetch(`${this.apiBaseUrl}/${entry.id}/pin`, {
                    method: 'PATCH',
                    headers: this.authHeaders
                });
                if (response.ok) {
                    await this.fetchEntries(); // re-sort with pinned entries on top
                    this.showToast(entry.pinned ? 'Entry unpinned' : 'Entry pinned');
                } else {
                    this.showToast('Could not update pin', 'error');
                }
            } catch (error) {
                console.error('Pin error:', error);
                this.showToast('Network error', 'error');
            }
        },

        formatDate(dateString) {
            const options = { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' };
            return new Date(dateString).toLocaleDateString(undefined, options);
        }
    }));
});