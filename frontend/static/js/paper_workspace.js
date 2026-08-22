document.addEventListener('alpine:init', () => {
    Alpine.data('paperWorkspace', (paperId, authToken) => ({
        // Global variables
        paperId: paperId,
        authToken: authToken,
        currentTab: 'abstract',
        
        // Tab 1: Abstract & Audio state
        abstractText: 'Loading abstract immediately...',
        ttsLang: 'en',
        ttsAccent: 'com',
        audioSpeed: 1.0,
        audioStatus: 'stopped', // stopped, loading, playing, paused, error
        cachedAudioKey: null,

        // Tab 2: Notes state
        notes: [],
        newPageNum: 1,
        newNoteContent: '',

        // Tab 3: Chat state
        messages: [{ sender: 'ai', text: 'Ask any question about this paper...', source: null }],
        chatQuery: '',
        chatLoading: false,

        get headers() {
            return {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.authToken}`
            };
        },

        init() {
            this.loadAbstract();
            this.loadNotes();

            // Listen for when audio finishes playing naturally
            this.$nextTick(() => {
                const player = document.getElementById('audio-player');
                if (player) {
                    player.onended = () => {
                        this.audioStatus = 'stopped';
                    };
                }
            });
        },

        async loadAbstract() {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/papers/${this.paperId}/overview`, { headers: this.headers });
                const data = await res.json();
                this.abstractText = data.abstract || "No abstract available for this paper.";
            } catch (err) {
                this.abstractText = "Failed to load abstract overview.";
            }
        },

        async loadNotes() {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/papers/${this.paperId}/notes`, { headers: this.headers });
                this.notes = await res.json();
            } catch (err) {
                console.error("Error loading notes", err);
            }
        },

        async saveNote() {
            if (!this.newNoteContent.trim()) return;
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/papers/${this.paperId}/notes`, {
                    method: 'POST',
                    headers: this.headers,
                    body: JSON.stringify({
                        page_number: parseInt(this.newPageNum) || 1,
                        note_content: this.newNoteContent
                    })
                });
                
                if (res.ok) {
                    this.notes.push({
                        page_number: parseInt(this.newPageNum) || 1,
                        note_content: this.newNoteContent
                    });
                    this.newNoteContent = ''; // Clear input field
                } else {
                    throw new Error("Failed to save note.");
                }
            } catch (err) {
                alert(err.message);
            }
        },

        async sendChatMessage() {
            if (!this.chatQuery.trim()) return;
            const q = this.chatQuery;
            this.messages.push({ sender: 'user', text: q, source: null });
            this.chatQuery = '';
            this.chatLoading = true;
            this.scrollToBottom();

            try {
                const res = await fetch(`http://127.0.0.1:8000/api/papers/${this.paperId}/chat`, {
                    method: 'POST',
                    headers: this.headers,
                    body: JSON.stringify({ question: q })
                });
                
                const data = await res.json();
                this.messages.push({ sender: 'ai', text: data.answer, source: data.source });
            } catch (err) {
                this.messages.push({ sender: 'ai', text: 'Error connecting to AI service.', source: null });
            } finally {
                this.chatLoading = false;
                this.scrollToBottom();
            }
        },

        scrollToBottom() {
            this.$nextTick(() => {
                const container = document.getElementById('chat-messages');
                if (container) container.scrollTop = container.scrollHeight;
            });
        },

        // --- TTS AUDIO METHODS ---
        
        onLanguageChange() {
            this.resetAudioPlayback();
        },

        setAudioSpeed(speed) {
            this.audioSpeed = speed;
            const player = document.getElementById('audio-player');
            if (player) player.playbackRate = speed;
        },

        resetAudioPlayback() {
            const player = document.getElementById('audio-player');
            if (player) {
                player.pause();
                player.src = "";
            }
            this.cachedAudioKey = null;
            this.audioStatus = 'stopped';
        },

        async playAudioSummary() {
            const player = document.getElementById('audio-player');
            if (!player) return;

            if (this.abstractText.includes("Loading") || this.abstractText.includes("Failed")) return;

            // Create a unique key so we know if the user changed the text/language/accent since last fetch
            const requestKey = `${this.ttsLang}-${this.ttsAccent}-${this.abstractText.substring(0, 30)}`;

            // 1. Toggle Pause/Play if audio is already loaded and settings haven't changed
            if (this.cachedAudioKey === requestKey && player.src) {
                if (!player.paused) {
                    player.pause();
                    this.audioStatus = 'paused';
                } else {
                    player.playbackRate = this.audioSpeed;
                    player.play();
                    this.audioStatus = 'playing';
                }
                return;
            }

            // 2. Fetch new audio from the backend
            this.audioStatus = 'loading';

            try {
                const res = await fetch(`http://127.0.0.1:8000/api/papers/tts`, {
                    method: 'POST',
                    headers: this.headers,
                    body: JSON.stringify({ 
                        text: this.abstractText,
                        lang: this.ttsLang,
                        accent: this.ttsAccent
                    })
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || "Audio generation failed");
                }

                // 3. Convert backend stream to playable frontend blob
                const blob = await res.blob();
                const audioUrl = URL.createObjectURL(blob);
                
                player.src = audioUrl;
                player.playbackRate = this.audioSpeed;
                player.play();

                this.cachedAudioKey = requestKey;
                this.audioStatus = 'playing';

            } catch (err) {
                console.error(err);
                this.audioStatus = 'error';
                setTimeout(() => { this.audioStatus = 'stopped'; }, 2500);
                alert(err.message || "Failed to generate audio summary. Ensure you have Premium access.");
            }
        }
    }));
});