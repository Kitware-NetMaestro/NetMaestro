export const dataStore = {
  // loadTick: incremented when "Load Data" is clicked to trigger plot updates
  loadTick: 0,

  // Currently selected run ID
  selectedRunId: null,

  async fetchRossData() {
    if (!this.selectedRunId) {
      return null;
    }
    const response = await fetch(`/api/v1/runs/${this.selectedRunId}/ross`);
    if (!response.ok) {
      throw new Error(`Failed to fetch ROSS data: ${response.statusText}`);
    }
    return await response.json();
  },

  async fetchEventData() {
    if (!this.selectedRunId) {
      return null;
    }
    const response = await fetch(`/api/v1/runs/${this.selectedRunId}/event`);
    if (!response.ok) {
      throw new Error(`Failed to fetch event data: ${response.statusText}`);
    }
    return await response.json();
  },

  async fetchModelData() {
    if (!this.selectedRunId) {
      return null;
    }
    const response = await fetch(`/api/v1/runs/${this.selectedRunId}/model`);
    if (!response.ok) {
      throw new Error(`Failed to fetch model data: ${response.statusText}`);
    }
    return await response.json();
  },

  /**
   * Select a run and trigger data reload from DB records.
   * @param {number} runId - The run primary key
   */
  selectRun(runId) {
    this.selectedRunId = runId;
    this.loadTick++;
  },
};
