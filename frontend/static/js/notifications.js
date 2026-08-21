document.addEventListener('alpine:init', () => {
    Alpine.data('notificationBell', (token) => ({
        authToken: token,
        open: false,
        unreadCount: 0,
        notifications: [],
        pollHandle: null,

        get authHeaders() {
            return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.authToken}` };
        },

        init() {
            this.fetchUnreadCount();
            this.fetchNotifications();
            // Lightweight polling, no WebSockets — matches this project's existing REST-only architecture.
            this.pollHandle = setInterval(() => {
                this.fetchUnreadCount();
                if (this.open) this.fetchNotifications();
            }, 25000);
        },

        async fetchUnreadCount() {
            try {
                const res = await fetch('http://127.0.0.1:8000/api/collaboration/notifications/unread-count', { headers: this.authHeaders });
                if (res.ok) { const json = await res.json(); this.unreadCount = json.unread_count; }
            } catch (err) { console.error(err); }
        },
        async fetchNotifications() {
            try {
                const res = await fetch('http://127.0.0.1:8000/api/collaboration/notifications', { headers: this.authHeaders });
                if (res.ok) this.notifications = await res.json();
            } catch (err) { console.error(err); }
        },
        async markRead(n) {
            if (n.is_read) return;
            n.is_read = true;
            this.unreadCount = Math.max(0, this.unreadCount - 1);
            try {
                await fetch(`http://127.0.0.1:8000/api/collaboration/notifications/${n.id}/read`, { method: 'POST', headers: this.authHeaders });
            } catch (err) { console.error(err); }
        },
        async markAllRead() {
            try {
                const res = await fetch('http://127.0.0.1:8000/api/collaboration/notifications/mark-all-read', { method: 'POST', headers: this.authHeaders });
                if (res.ok) {
                    this.notifications.forEach(n => n.is_read = true);
                    this.unreadCount = 0;
                }
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
            const diffMs = Date.now() - new Date(dateString).getTime();
            const mins = Math.floor(diffMs / 60000);
            if (mins < 1) return 'just now';
            if (mins < 60) return `${mins}m ago`;
            const hrs = Math.floor(mins / 60);
            if (hrs < 24) return `${hrs}h ago`;
            const days = Math.floor(hrs / 24);
            return `${days}d ago`;
        }
    }));
});