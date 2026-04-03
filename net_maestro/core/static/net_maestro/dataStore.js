document.addEventListener('alpine:init', () => {
  Alpine.store('dataStore', {
    // loadTick: incremented to trigger plot updates
    loadTick: 0,

    // Currently selected run ID (null = use file-based endpoints)
    selectedRunId: null,

    // Cache storage for API responses
    rossDataCache: null,
    rossDataPromise: null,
    eventDataCache: null,
    eventDataPromise: null,
    modelDataCache: null,
    modelDataPromise: null,

    async fetchRossData() {
      // Return cached data if available
      if (this.rossDataCache) {
        return this.rossDataCache;
      }

      // Return existing promise if request is in-flight
      if (this.rossDataPromise) {
        return this.rossDataPromise;
      }

      // Make new request — use run-based endpoint if a run is selected
      const url = this.selectedRunId
        ? `/api/v1/runs/${this.selectedRunId}/ross`
        : '/api/v1/data/ross';
      this.rossDataPromise = fetch(url)
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Failed to fetch ROSS data: ${response.statusText}`);
          }
          const data = await response.json();
          this.rossDataCache = data;
          this.rossDataPromise = null;
          return data;
        })
        .catch((error) => {
          this.rossDataPromise = null;
          throw error;
        });
      return this.rossDataPromise;
    },

    async fetchEventData() {
      if (this.eventDataCache) {
        return this.eventDataCache;
      }

      if (this.eventDataPromise) {
        return this.eventDataPromise;
      }

      const eventUrl = this.selectedRunId
        ? `/api/v1/runs/${this.selectedRunId}/event`
        : '/api/v1/data/event';
      this.eventDataPromise = await fetch(eventUrl)
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Failed to fetch Event data: ${response.statusText}`);
          }
          const data = await response.json();
          this.eventDataCache = data;
          this.eventDataPromise = null;
          return data;
        })
        .catch((error) => {
          this.eventDataPromise = null;
          throw error;
        });
      return this.eventDataPromise;
    },

    async fetchModelData() {
      if (this.modelDataCache) {
        return this.modelDataCache;
      }

      if (this.modelDataPromise) {
        return this.modelDataPromise;
      }

      const modelUrl = this.selectedRunId
        ? `/api/v1/runs/${this.selectedRunId}/model`
        : '/api/v1/data/model';
      this.modelDataPromise = await fetch(modelUrl)
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Failed to fetch Model data: ${response.statusText}`);
          }
          const data = await response.json();
          this.modelDataCache = data;
          this.modelDataPromise = null;
          return data;
        })
        .catch((error) => {
          this.modelDataPromise = null;
          throw error;
        });
      return this.modelDataPromise;
    },

    /**
     * Clear cached data. Call when new data files are selected.
     */
    clearCache() {
      this.rossDataCache = null;
      this.rossDataPromise = null;
      this.eventDataCache = null;
      this.eventDataPromise = null;
      this.modelDataCache = null;
      this.modelDataPromise = null;
    },

    /**
     * Select a run and trigger data reload from DB records.
     * @param {number} runId - The run primary key
     */
    selectRun(runId) {
      this.selectedRunId = runId;
      this.clearCache();
      this.loadTick++;
    },
  });
});
