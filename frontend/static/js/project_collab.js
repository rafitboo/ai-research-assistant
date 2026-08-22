document.addEventListener('alpine:init', () => {
    Alpine.data('projectCollabApp', (projectId, token) => ({
        projectId: projectId,
        authToken: token,
        members: [],
        invitations: [],
        posts: [],
        auditLog: [],
        inviteEmail: '',
        inviteRole: 'Collaborator',
        newPostContent: '',
        replyBuffers: {},
        apiBaseUrl: 'http://127.0.0.1:8000/api/collaboration',

        get authHeaders() {
            return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.authToken}` };
        },

        init() {
            this.fetchMembers();
            this.fetchInvitations();
            this.fetchPosts();
            this.fetchAuditLog();
        },

        async fetchAuditLog() {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/projects/${this.projectId}/audit-log`, { headers: this.authHeaders });
                if (res.ok) this.auditLog = await res.json();
            } catch (err) { console.error(err); }
        },

        async fetchMembers() {
            try {
                const res = await fetch(`${this.apiBaseUrl}/projects/${this.projectId}/members`, { headers: this.authHeaders });
                if (res.ok) this.members = await res.json();
            } catch (err) { console.error(err); }
        },

        async fetchInvitations() {
            try {
                const res = await fetch(`${this.apiBaseUrl}/projects/${this.projectId}/invitations`, { headers: this.authHeaders });
                if (res.ok) this.invitations = await res.json();
            } catch (err) { console.error(err); }
        },

        async sendInvite() {
            try {
                const res = await fetch(`${this.apiBaseUrl}/projects/${this.projectId}/invite`, {
                    method: 'POST', headers: this.authHeaders,
                    body: JSON.stringify({ email: this.inviteEmail, role: this.inviteRole })
                });
                if (res.ok) {
                    this.inviteEmail = '';
                    this.fetchInvitations();
                    this.fetchAuditLog();
                } else {
                    const err = await res.json().catch(() => ({}));
                    alert(err.detail || "Could not send invitation.");
                }
            } catch (err) { console.error(err); }
        },

        async resendInvite(id) {
            try {
                const res = await fetch(`${this.apiBaseUrl}/invitations/${id}/resend`, { method: 'POST', headers: this.authHeaders });
                if (res.ok) { this.fetchInvitations(); }
            } catch (err) { console.error(err); }
        },

        async fetchPosts() {
            try {
                const res = await fetch(`${this.apiBaseUrl}/projects/${this.projectId}/posts`, { headers: this.authHeaders });
                if (res.ok) this.posts = await res.json();
            } catch (err) { console.error(err); }
        },

        async createPost(parentId) {
            const content = parentId ? this.replyBuffers[parentId] : this.newPostContent;
            if (!content || !content.trim()) return;

            try {
                const res = await fetch(`${this.apiBaseUrl}/projects/${this.projectId}/posts`, {
                    method: 'POST', headers: this.authHeaders,
                    body: JSON.stringify({ content: content, parent_id: parentId })
                });
                if (res.ok) {
                    if (parentId) this.replyBuffers[parentId] = '';                    
                    else this.newPostContent = '';
                    this.fetchPosts();
                    this.fetchAuditLog();
                }
            } catch (err) { console.error(err); }
        },

        formatDate(dateString) {
            return new Date(dateString).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        }
    }));
});