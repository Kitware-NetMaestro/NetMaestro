/**
 * Alpine.js component for the data file selector dropdown.
 * Manages file selection state and API interactions.
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('dataFileSelector', () => ({
        open: false,
        refreshing: false,
        loaded: false,
        files: { simulations: [], events: [], models: [] },
        selected: { simulations: null, events: null, models: null },

        /**
         * Fetch available files and current selections from API.
         */
        async refresh() {
            this.refreshing = true;
            try {
                const response = await fetch('/api/v1/data/files');
                const payload = await response.json();
                this.files = payload.files;
                this.selected = payload.selected;
                this.loaded = true;
            } finally {
                this.refreshing = false;
            }
        },

        /**
         * Update selected file for a category (persists in session).
         *
         * @param {string} category - The category (simulations, events, or models)
         * @param {string} file - The filename to select
         */
        async select(category, file) {
            await fetch('/api/v1/data/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category, file }),
            });
            this.selected[category] = file;
        },
    }));
});
