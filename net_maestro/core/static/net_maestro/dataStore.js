export const dataStore = {
  // loadTick: incremented when "Load Data" is clicked to trigger plot updates
  loadTick: 0,

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

    // Make new request
    this.rossDataPromise = fetch('/api/v1/data/ross')
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

    this.eventDataPromise = await fetch('/api/v1/data/event')
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

    this.modelDataPromise = await fetch('/api/v1/data/model')
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
};
