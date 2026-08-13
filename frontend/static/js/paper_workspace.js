document.addEventListener('alpine:init', () => {
    Alpine.data('paperWorkspace', (paperId, authToken) => ({
        abstractText: 'Loading abstract immediately...',
        notes: [],
        newPageNum: 1,
        newNoteContent: '',
        messages: [],
        chatQuery: '',
        chatLoading: false,

        init() {
            // Fetch abstract immediately upon page load
            this.loadAbstract(paperId, authToken);
            this.loadNotes(paperId, authToken);
        },

        loadAbstract(id, token) {
            fetch(`http://127.0.0.1:8000/api/papers/${id}/overview`, {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            .then(res => res.json())
            .then(data => {
                this.abstractText = data.abstract || "No abstract available for this paper.";
            })
            .catch(err => {
                this.abstractText = "Failed to load abstract overview.";
            });
        },

        loadNotes(id, token) {
            fetch(`http://127.0.0.1:8000/api/papers/${id}/notes`, {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            .then(res => res.json())
            .then(data => {
                this.notes = data;
            })
            .catch(err => console.error("Error loading notes", err));
        },

        saveNote(id, token) {
            if (!this.newNoteContent.trim()) return;
            fetch(`http://127.0.0.1:8000/api/papers/${id}/notes`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    page_number: parseInt(this.newPageNum) || 1,
                    note_content: this.newNoteContent
                })
            })
            .then(res => res.json())
            .then(data => {
                this.notes.push({
                    page_number: this.newPageNum,
                    note_content: this.newNoteContent
                });
                this.newNoteContent = '';
            })
            .catch(err => alert("Failed to save note."));
        },

        sendChatMessage(id, token) {
            if (!this.chatQuery.trim()) return;
            const q = this.chatQuery;
            this.messages.push({ sender: 'user', text: q, source: null });
            this.chatQuery = '';
            this.chatLoading = true;

            fetch(`http://127.0.0.1:8000/api/papers/${id}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ question: q })
            })
            .then(res => res.json())
            .then(data => {
                this.messages.push({ sender: 'ai', text: data.answer, source: data.source });
                this.chatLoading = false;
            })
            .catch(err => {
                this.messages.push({ sender: 'ai', text: 'Error connecting to AI service.', source: null });
                this.chatLoading = false;
            });
        }
    }));
});