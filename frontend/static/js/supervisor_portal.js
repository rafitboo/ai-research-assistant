document.addEventListener('alpine:init', () => {
    Alpine.data('supervisorPortalApp', (token) => ({
        authToken: token,
        apiBaseUrl: '/api/supervisor-portal',

        projects: [],
        supervisors: [],
        meetings: [],
        milestones: [],

        selectedProjectId: '',
        activeTab: 'meetings',
        loading: false,
        errorMessage: '',
        successMessage: '',

        currentUserId: null,
        currentUserRole: '',

        meetingForm: {
            supervisor_id: '',
            start_at: '',
            end_at: '',
            topic: '',
            notes: ''
        },

        milestoneForm: {
            title: '',
            description: '',
            due_date: ''
        },

        reviewComment: {},

        get authHeaders() {
            return {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.authToken}`
            };
        },

        get selectedProject() {
            return this.projects.find((p) => Number(p.id) === Number(this.selectedProjectId)) || null;
        },

        get isSupervisor() {
            return this.selectedProject?.role === 'Supervisor';
        },

        get reviewQueue() {
            return this.milestones.filter((m) => m.status === 'Pending Review');
        },

        get upcomingMeetings() {
            return this.meetings.filter((m) => ['Pending', 'Approved'].includes(m.status));
        },

        async init() {
            try {
                const me = await this.request('/auth/me', 'GET', null, '/api');
                this.currentUserId = me.id;
                this.currentUserRole = me.role;
            } catch (_) {
                // The portal itself remains usable through project membership.
            }

            await this.loadProjects();
        },

        async request(path, method = 'GET', body = null, baseUrl = this.apiBaseUrl) {
            const options = { method, headers: this.authHeaders };
            if (body !== null) options.body = JSON.stringify(body);

            const response = await fetch(`${baseUrl}${path}`, options);
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(data.detail || 'Request failed.');
            }

            return data;
        },

        async loadProjects() {
            try {
                this.setLoading(true);
                this.projects = await this.request('/projects');

                if (this.projects.length > 0) {
                    this.selectedProjectId = String(this.projects[0].id);
                    await this.loadProjectData();
                }
            } catch (error) {
                this.showError(error.message);
            } finally {
                this.setLoading(false);
            }
        },

        async changeProject() {
            await this.loadProjectData();
        },

        async loadProjectData() {
            if (!this.selectedProjectId) return;

            try {
                this.setLoading(true);
                this.clearMessages();

                const [supervisors, meetings, milestones] = await Promise.all([
                    this.request(`/projects/${this.selectedProjectId}/supervisors`),
                    this.request(`/projects/${this.selectedProjectId}/meetings`),
                    this.request(`/projects/${this.selectedProjectId}/milestones`)
                ]);

                this.supervisors = supervisors;
                this.meetings = meetings;
                this.milestones = milestones;

                if (!this.meetingForm.supervisor_id && this.supervisors.length > 0) {
                    this.meetingForm.supervisor_id = String(this.supervisors[0].id);
                }
            } catch (error) {
                this.showError(error.message);
            } finally {
                this.setLoading(false);
            }
        },

        async submitMeetingRequest() {
            this.clearMessages();

            if (!this.selectedProjectId || !this.meetingForm.supervisor_id) {
                this.showError('Please select a project and supervisor.');
                return;
            }

            if (!this.meetingForm.start_at || !this.meetingForm.end_at) {
                this.showError('Please choose both a start and end time.');
                return;
            }

            try {
                this.setLoading(true);

                await this.request('/meetings/request', 'POST', {
                    project_id: Number(this.selectedProjectId),
                    supervisor_id: Number(this.meetingForm.supervisor_id),
                    start_at: new Date(this.meetingForm.start_at).toISOString(),
                    end_at: new Date(this.meetingForm.end_at).toISOString(),
                    topic: this.meetingForm.topic,
                    notes: this.meetingForm.notes
                });

                this.meetingForm.start_at = '';
                this.meetingForm.end_at = '';
                this.meetingForm.topic = '';
                this.meetingForm.notes = '';

                this.showSuccess('Meeting request submitted.');
                await this.loadProjectData();
            } catch (error) {
                this.showError(error.message);
            } finally {
                this.setLoading(false);
            }
        },

        async decideMeeting(meetingId, decision) {
            const responseText = decision === 'Approved'
                ? 'Approved from the supervisor portal.'
                : (window.prompt('Optional response to the student:') || '');

            try {
                this.setLoading(true);
                await this.request(`/meetings/${meetingId}/decision`, 'POST', {
                    decision,
                    response: responseText
                });
                this.showSuccess(`Meeting ${decision.toLowerCase()}.`);
                await this.loadProjectData();
            } catch (error) {
                this.showError(error.message);
            } finally {
                this.setLoading(false);
            }
        },

        async cancelMeeting(meetingId) {
            if (!window.confirm('Cancel this meeting/request?')) return;

            try {
                this.setLoading(true);
                await this.request(`/meetings/${meetingId}/cancel`, 'POST');
                this.showSuccess('Meeting cancelled.');
                await this.loadProjectData();
            } catch (error) {
                this.showError(error.message);
            } finally {
                this.setLoading(false);
            }
        },

        async createMilestone() {
            this.clearMessages();

            if (!this.milestoneForm.title.trim()) {
                this.showError('Milestone title is required.');
                return;
            }

            try {
                this.setLoading(true);
                await this.request('/milestones', 'POST', {
                    project_id: Number(this.selectedProjectId),
                    title: this.milestoneForm.title,
                    description: this.milestoneForm.description,
                    due_date: this.milestoneForm.due_date || null
                });

                this.milestoneForm.title = '';
                this.milestoneForm.description = '';
                this.milestoneForm.due_date = '';

                this.showSuccess('Milestone created as a draft.');
                await this.loadProjectData();
            } catch (error) {
                this.showError(error.message);
            } finally {
                this.setLoading(false);
            }
        },

        async submitMilestone(milestoneId) {
            try {
                this.setLoading(true);
                await this.request(`/milestones/${milestoneId}/submit`, 'POST');
                this.showSuccess('Milestone submitted for supervisor review.');
                await this.loadProjectData();
            } catch (error) {
                this.showError(error.message);
            } finally {
                this.setLoading(false);
            }
        },

        async reviewMilestone(milestoneId, decision) {
            const comments = this.reviewComment[milestoneId] || '';

            if (decision === 'Revision Requested' && !comments.trim()) {
                this.showError('Please add revision comments before requesting changes.');
                return;
            }

            try {
                this.setLoading(true);
                await this.request(`/milestones/${milestoneId}/review`, 'POST', {
                    decision,
                    comments
                });
                this.reviewComment[milestoneId] = '';
                this.showSuccess(`Milestone ${decision.toLowerCase()}.`);
                await this.loadProjectData();
            } catch (error) {
                this.showError(error.message);
            } finally {
                this.setLoading(false);
            }
        },

        formatDateTime(value) {
            if (!value) return '—';
            return new Date(value).toLocaleString(undefined, {
                dateStyle: 'medium',
                timeStyle: 'short'
            });
        },

        formatStatus(status) {
            return status.replaceAll('_', ' ');
        },

        statusClasses(status) {
            const map = {
                Pending: 'bg-amber-100 text-amber-700',
                Approved: 'bg-emerald-100 text-emerald-700',
                Declined: 'bg-rose-100 text-rose-700',
                Cancelled: 'bg-slate-100 text-slate-600',
                Draft: 'bg-slate-100 text-slate-700',
                'Pending Review': 'bg-indigo-100 text-indigo-700',
                'Revision Requested': 'bg-orange-100 text-orange-700'
            };
            return map[status] || 'bg-slate-100 text-slate-700';
        },

        setLoading(value) {
            this.loading = value;
        },

        clearMessages() {
            this.errorMessage = '';
            this.successMessage = '';
        },

        showError(message) {
            this.errorMessage = message;
            this.successMessage = '';
        },

        showSuccess(message) {
            this.successMessage = message;
            this.errorMessage = '';
        }
    }));
});
