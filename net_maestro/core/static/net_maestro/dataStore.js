document.addEventListener('alpine:init', () => {
    Alpine.store('dataStore', {
        // loadTick: incremented when "Load Data" is clicked to trigger plot updates
        loadTick: 0,

        // Cache storage for API responses
        rossDataCache: null,
        rossDataPromise: null,

        async fetchRossData() {
            // Return cached data if available
            if (this.rossDataCache) {
                return this.rossDataCache;
            }

            // Return existing promise if request is in-flight
            if (this.rossDataPromise) {
                return this.rossDataPromise;
            }

            // Make new request
            this.rossDataPromise = fetch('/api/v1/data/ross')
            .then(async response => {
                if (!response.ok) {
                    throw new Error(`Failed to fetch ROSS data: ${response.statusText}`);
                }
                const data = await response.json();
                this.rossDataCache = data;
                this.rossDataPromise = null;
                return data;
            })
            .catch(error => {
                this.rossDataPromise = null;
                throw error;
            });
            return this.rossDataPromise;
        },

        /**
         * Clear cached data. Call when new data files are selected.
         */
        clearCache() {
            this.rossDataCache = null;
            this.rossDataPromise = null;
        }
    });
});
