document.addEventListener('alpine:init', () => {
    Alpine.data('smartFolders', () => ({
        folders: [],
        selectedFolder: null,
        folderPapers: [],
        recommendations: [],
        folderInsights: null,
        
        newFolderName: '',
        newFolderColor: 'indigo',
        
        // UI States
        isLoadingFolders: false,
        isCreating: false,
        isLoadingRecs: false,
        showModal: false,
        libraryPapers: [],
        isLoadingLibrary: false,

        apiBase: '/api/smart-folders',
        
        get headers() {
            return {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${window.USER_TOKEN}`
            };
        },

        get availableLibraryPapers() {
            const currentFolderIds = new Set(this.folderPapers.map(p => p.id));
            return this.libraryPapers.filter(p => !currentFolderIds.has(p.id));
        },

        init() { this.fetchFolders(); },

        async fetchFolders() {
            this.isLoadingFolders = true;
            try {
                const res = await fetch(`${this.apiBase}/`, { headers: this.headers });
                if (res.ok) this.folders = await res.json();
            } catch (err) { console.error(err); } 
            finally { this.isLoadingFolders = false; }
        },

        async createFolder() {
            if (!this.newFolderName.trim()) return;
            this.isCreating = true;
            try {
                const res = await fetch(`${this.apiBase}/create?name=${encodeURIComponent(this.newFolderName)}&color=${this.newFolderColor}`, {
                    method: 'POST', headers: this.headers
                });
                if (res.ok) {
                    const newFolder = await res.json();
                    this.folders.push({ ...newFolder, paper_count: 0 });
                    this.newFolderName = '';
                    this.selectFolder(newFolder);
                }
            } catch (err) { console.error(err); } 
            finally { this.isCreating = false; }
        },

        async selectFolder(folder) {
            this.selectedFolder = folder;
            this.folderPapers = [];
            this.recommendations = [];
            this.folderInsights = null;
            
            await this.fetchFolderContents(folder.id);
            await this.fetchFolderInsights(folder.id);
            await this.fetchRecommendations(folder.id);
        },

        // --- NEW: Delete Folder Method ---
        async deleteFolder(folderId) {
            if (!confirm("Are you sure you want to completely delete this folder? This action cannot be undone.")) return;
            
            try {
                const res = await fetch(`${this.apiBase}/${folderId}`, {
                    method: 'DELETE', 
                    headers: this.headers
                });
                
                if (res.ok) {
                    // Remove from list
                    this.folders = this.folders.filter(f => f.id !== folderId);
                    
                    // Clear right panel if the deleted folder was actively selected
                    if (this.selectedFolder && this.selectedFolder.id === folderId) {
                        this.selectedFolder = null;
                        this.folderPapers = [];
                        this.recommendations = [];
                        this.folderInsights = null;
                    }
                }
            } catch (err) {
                console.error("Error deleting folder:", err);
            }
        },

        async fetchFolderContents(folderId) {
            try {
                const res = await fetch(`${this.apiBase}/${folderId}/papers`, { headers: this.headers });
                if (res.ok) this.folderPapers = await res.json();
            } catch (err) { console.error(err); }
        },

        async fetchFolderInsights(folderId) {
            try {
                const res = await fetch(`${this.apiBase}/${folderId}/insights`, { headers: this.headers });
                if (res.ok) this.folderInsights = await res.json();
            } catch (err) { console.error(err); }
        },

        async fetchRecommendations(folderId) {
            this.isLoadingRecs = true;
            try {
                const res = await fetch(`${this.apiBase}/${folderId}/recommendations`, { headers: this.headers });
                if (res.ok) this.recommendations = await res.json();
            } catch (err) { console.error(err); } 
            finally { this.isLoadingRecs = false; }
        },

        async addPaperToFolder(paperId) {
            if (!this.selectedFolder) return;
            try {
                const res = await fetch(`${this.apiBase}/${this.selectedFolder.id}/add-paper/${paperId}`, {
                    method: 'POST', headers: this.headers
                });
                if (res.ok) {
                    this.recommendations = this.recommendations.filter(r => r.id !== paperId);
                    await this.fetchFolderContents(this.selectedFolder.id);
                    await this.fetchFolderInsights(this.selectedFolder.id);
                    
                    const folderIndex = this.folders.findIndex(f => f.id === this.selectedFolder.id);
                    if(folderIndex !== -1) this.folders[folderIndex].paper_count++;
                }
            } catch (err) { console.error(err); }
        },

        async removePaperFromFolder(paperId) {
            if (!this.selectedFolder) return;
            if (!confirm("Remove this paper from the smart folder?")) return;
            try {
                const res = await fetch(`${this.apiBase}/${this.selectedFolder.id}/remove-paper/${paperId}`, {
                    method: 'DELETE', headers: this.headers
                });
                if (res.ok) {
                    this.folderPapers = this.folderPapers.filter(p => p.id !== paperId);
                    const folderIndex = this.folders.findIndex(f => f.id === this.selectedFolder.id);
                    if(folderIndex !== -1) this.folders[folderIndex].paper_count--;
                    
                    await this.fetchFolderInsights(this.selectedFolder.id);
                    await this.fetchRecommendations(this.selectedFolder.id);
                }
            } catch (err) { console.error(err); }
        },

        openPaperWorkspace(paperId) { window.location.href = `/papers/${paperId}/workspace`; },

        async dismissRecommendation(paperId) {
            try {
                this.recommendations = this.recommendations.filter(r => r.id !== paperId);
                await fetch(`${this.apiBase}/recommendations/${paperId}/dismiss`, { method: 'POST', headers: this.headers });
            } catch (err) { console.error(err); }
        },

        async openLibraryModal() {
            this.showModal = true;
            if (this.libraryPapers.length === 0) {
                this.isLoadingLibrary = true;
                try {
                    const res = await fetch(`/api/papers/`, { headers: this.headers });
                    if (res.ok) this.libraryPapers = await res.json();
                } catch (err) { console.error(err); } 
                finally { this.isLoadingLibrary = false; }
            }
        },

        async addPaperFromModal(paperId) {
            await this.addPaperToFolder(paperId);
            this.showModal = false; 
        }
    }));
});