document.addEventListener('alpine:init', () => {
    Alpine.data('taskBoardApp', (projectId, token) => ({
        projectId: projectId,
        authToken: token,
        tasks: [],
        milestones: [],
        timeline: [],
        members: [],
        currentUserId: null,
        showNewTask: false,
        selectedTask: null,
        dragTaskId: null,
        form: { title: '', description: '', due_date: '', milestone_id: '', new_milestone_title: '', depends_on_id: '', assignee_id: '' },
        apiBaseUrl: 'http://127.0.0.1:8000/api/task-board',
        collabApiBaseUrl: 'http://127.0.0.1:8000/api/collaboration',

        get authHeaders() {
            return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.authToken}` };
        },

        init() {
            this.currentUserId = this.parseUserIdFromToken(this.authToken);
            this.fetchTasks();
            this.fetchMilestones();
            this.fetchTimeline();
            this.fetchMembers();
        },

        parseUserIdFromToken(token) {
            try {
                const payload = JSON.parse(atob(token.split('.')[1]));
                const id = payload.user_id ?? payload.sub ?? payload.id;
                return id != null ? parseInt(id) : null;
            } catch (err) { return null; }
        },

        async fetchMembers() {
            try {
                const res = await fetch(`${this.collabApiBaseUrl}/projects/${this.projectId}/members`, { headers: this.authHeaders });
                if (res.ok) this.members = await res.json();
            } catch (err) { console.error(err); }
        },

        // "Assigned to me" should read "Assigned to you", never the raw name.
        assigneeLabel(t) {
            if (!t.assignee_id) return 'Unassigned';
            return t.assignee_id === this.currentUserId ? 'Assigned to you' : `Assigned to ${t.assignee_name}`;
        },

        get progressPct() {
            if (!this.tasks.length) return 0;
            return Math.round((this.tasksByStatus('Done').length / this.tasks.length) * 100);
        },

        get doneCount() {
            return this.tasksByStatus('Done').length;
        },

        get isOwner() {
            const me = this.members.find(m => m.user_id === this.currentUserId);
            return !!me && me.role === 'Owner';
        },

        canDelete(t) {
            return t.created_by === this.currentUserId || this.isOwner;
        },

        canDrag(t) {
            // Only the assignee (or nobody assigned yet) can move a task, and a Done task
            // can't be dragged back — both match the backend checks in update_task_status.
            if (t.status === 'Done') return false;
            return !t.assignee_id || t.assignee_id === this.currentUserId;
        },

        openTask(t) {
            this.selectedTask = t;
        },

        closeTask() {
            this.selectedTask = null;
        },

        tasksByStatus(status) {
            return this.tasks.filter(t => t.status === status);
        },

        async fetchTasks() {
            try {
                const res = await fetch(`${this.apiBaseUrl}/projects/${this.projectId}/tasks`, { headers: this.authHeaders });
                if (res.ok) this.tasks = await res.json();
            } catch (err) { console.error(err); }
        },

        async fetchMilestones() {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/supervisor-portal/projects/${this.projectId}/milestones`, { headers: this.authHeaders });
                if (res.ok) this.milestones = await res.json();
            } catch (err) { console.error(err); }
        },

        async fetchTimeline() {
            try {
                const res = await fetch(`${this.apiBaseUrl}/projects/${this.projectId}/timeline`, { headers: this.authHeaders });
                if (res.ok) this.timeline = await res.json();
            } catch (err) { console.error(err); }
        },

        async refreshAll() {
            await Promise.all([this.fetchTasks(), this.fetchTimeline()]);
        },

async createTask() {
    if (!this.form.title.trim()) return;

    const isNewMilestone = this.form.milestone_id === 'new';
    const payload = {
        project_id: this.projectId,
        title: this.form.title,
        description: this.form.description || null,
        due_date: this.form.due_date || null,
        milestone_id: isNewMilestone ? null : (this.form.milestone_id ? parseInt(this.form.milestone_id) : null),
        milestone_title: isNewMilestone ? (this.form.new_milestone_title || null) : null,
        depends_on_id: this.form.depends_on_id ? parseInt(this.form.depends_on_id) : null,
        assignee_id: this.form.assignee_id ? parseInt(this.form.assignee_id) : null,
    };

    try {
        const res = await fetch(`${this.apiBaseUrl}/tasks`, {
            method: 'POST',
            headers: this.authHeaders,
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            this.form = { title: '', description: '', due_date: '', milestone_id: '', new_milestone_title: '', depends_on_id: '', assignee_id: '' };
            this.showNewTask = false;
            await this.fetchMilestones();
            await this.refreshAll();
        } else {
            const err = await res.json().catch(() => ({}));
            alert(err.detail || 'Could not create task.');
        }
    } catch (err) { console.error(err); }
},

        async deleteTask(t) {
            if (!this.canDelete(t)) {
                alert("Only the task's creator or the project owner can delete it.");
                return;
            }
            if (!confirm('Delete this task?')) return;
            try {
                const res = await fetch(`${this.apiBaseUrl}/tasks/${t.id}`, { method: 'DELETE', headers: this.authHeaders });
                if (res.ok) {
                    if (this.selectedTask && this.selectedTask.id === t.id) this.selectedTask = null;
                    await this.refreshAll();
                } else {
                    const err = await res.json().catch(() => ({}));
                    alert(err.detail || 'Could not delete task.');
                }
            } catch (err) { console.error(err); }
        },

        async onDrop(newStatus) {
            const taskId = this.dragTaskId;
            const dragged = this.tasks.find(t => t.id === taskId);
            this.dragTaskId = null;
            if (!taskId) return;
            if (dragged && dragged.status === 'Done' && newStatus !== 'Done') {
                alert("This task is already Done. Reopening isn't supported from the board.");
                return;
            }
            try {
                const res = await fetch(`${this.apiBaseUrl}/tasks/${taskId}/status`, {
                    method: 'POST', headers: this.authHeaders,
                    body: JSON.stringify({ status: newStatus })
                });
                if (res.ok) {
                    await this.refreshAll();
                } else {
                    const err = await res.json().catch(() => ({}));
                    alert(err.detail || 'Could not move task.');
                }
            } catch (err) { console.error(err); }
        }
    }));
});