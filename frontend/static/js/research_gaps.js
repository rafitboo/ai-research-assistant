document.addEventListener("alpine:init", () => {
    Alpine.data("researchGapApp", (token) => ({
        authToken: token,
        papers: [],
        searchText: "",
        selectedPaperIds: [],
        selectedPapers: [],
        gaps: [],
        errorMessage: "",
        isLoading: false,
        hasGenerated: false,

        get apiBaseUrl() {
            return "http://127.0.0.1:8000/api";
        },

        get authHeaders() {
            return {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${this.authToken}`,
            };
        },

        get filteredPapers() {
            const q = this.searchText.trim().toLowerCase();

            if (!q) {
                return this.papers;
            }

            return this.papers.filter((paper) =>
                (paper.title || "").toLowerCase().includes(q) ||
                (paper.author || "").toLowerCase().includes(q) ||
                (paper.topic || "").toLowerCase().includes(q) ||
                (paper.research_area || "").toLowerCase().includes(q)
            );
        },

        async init() {
            await this.loadPapers();
        },

        async loadPapers() {
            try {
                const response = await fetch(
                    `${this.apiBaseUrl}/papers/`,
                    { headers: this.authHeaders }
                );

                if (!response.ok) {
                    throw new Error("Could not load the paper library.");
                }

                this.papers = await response.json();
            } catch (error) {
                console.error(error);
                this.errorMessage = error.message;
            }
        },

        isSelected(paperId) {
            return this.selectedPaperIds.includes(paperId);
        },

        togglePaper(paperId) {
            if (this.isSelected(paperId)) {
                this.selectedPaperIds =
                    this.selectedPaperIds.filter((id) => id !== paperId);
                return;
            }

            if (this.selectedPaperIds.length >= 10) {
                this.errorMessage = "You can select a maximum of 10 papers.";
                return;
            }

            this.selectedPaperIds.push(paperId);
            this.errorMessage = "";
        },

        removeSelected(paperId) {
            this.selectedPaperIds =
                this.selectedPaperIds.filter((id) => id !== paperId);
        },

        clearSelection() {
            this.selectedPaperIds = [];
        },

        resetResults() {
            this.gaps = [];
            this.selectedPapers = [];
            this.hasGenerated = false;
        },

        async generateGaps() {
            this.errorMessage = "";
            this.hasGenerated = false;
            this.gaps = [];
            this.selectedPapers = [];

            if (this.selectedPaperIds.length < 2) {
                this.errorMessage = "Please select at least two papers.";
                return;
            }

            this.isLoading = true;

            try {
                const response = await fetch(
                    `${this.apiBaseUrl}/research-gaps/generate`,
                    {
                        method: "POST",
                        headers: this.authHeaders,
                        body: JSON.stringify({
                            paper_ids: this.selectedPaperIds,
                        }),
                    }
                );

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(
                        data.detail || "Failed to generate research gaps."
                    );
                }

                this.selectedPapers = data.selected_papers || [];
                this.gaps = data.gaps || [];
                this.hasGenerated = true;
            } catch (error) {
                console.error(error);
                this.errorMessage =
                    error.message ||
                    "Something went wrong while generating the research gaps.";
            } finally {
                this.isLoading = false;
            }
        },
    }));
});
