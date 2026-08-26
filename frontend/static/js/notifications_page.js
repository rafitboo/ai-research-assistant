document.addEventListener('alpine:init', () => {
    Alpine.data('notificationsPage', (token) => ({
        authToken: token,
        notifications: [],
        filter: 'all',

        get authHeaders() {
            return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.authToken}` };
        },
        get filteredNotifications() {
            if (this.filter === 'all') return this.notifications;
            if (this.filter === 'unread') return this.notifications.filter(n => !n.is_read);
            if (this.filter === 'milestones') return this.notifications.filter(n => (n.type || '').startsWith('milestone'));
            if (this.filter === 'reviews') return this.notifications.filter(n => (n.type || '').includes('review') || (n.type || '').includes('meeting'));
            if (this.filter === 'projects') return this.notifications.filter(n => ['mention', 'project_invitation', 'invitation_accepted', 'discussion.posted'].includes(n.type));
            return this.notifications;
        },

        init() { this.fetchNotifications(); },
        async fetchNotifications() {
            try {
                const res = await fetch('/api/collaboration/notifications?limit=200', { headers: this.authHeaders });
                if (res.ok) this.notifications = await res.json();
            } catch (err) { console.error(err); }
        },
        async markRead(n) {
            if (n.is_read) return;
            n.is_read = true;
            try {
                await fetch(`/api/collaboration/notifications/${n.id}/read`, { method: 'POST', headers: this.authHeaders });
            } catch (err) { console.error(err); }
        },
        async markAllRead() {
            try {
                const res = await fetch('/api/collaboration/notifications/mark-all-read', { method: 'POST', headers: this.authHeaders });
                if (res.ok) this.notifications.forEach(n => n.is_read = true);
            } catch (err) { console.error(err); }
        },
        typeIcon(type) {
            const icons = {
                mention: '💬', milestone_submitted: '📤', milestone_approved: '✅',
                milestone_revision: '✏️', milestone_overdue: '⏰', project_invitation: '✉️',
                invitation_accepted: '🤝', meeting_requested: '📅', meeting_decided: '📅',
            };
            return icons[type] || '🔔';
        },
        formatTime(dateString) {
            return new Date(dateString).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        }
    }));
});