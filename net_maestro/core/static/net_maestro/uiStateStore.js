/**
 * Alpine.js store for UI state persistence across navigation.
 * Handles component preferences like axis selections, metrics, etc.
 */
document.addEventListener('alpine:init', () => {
  Alpine.store('uiStateStore', {
    // UI state persistence for plot component preferences
    uiState: {
      scatterPlot: {
        selectedXAxis: 'events_processed',
        selectedYAxis: 'events_rolled_back',
      },
      timePlot: {
        selectedXAxis: 'virtual_time',
        selectedYAxis: 'events_processed',
      },
      networkTimePlot: {
        selectedXAxis: 'virtual_time',
        selectedYAxis: 'send_count',
      },
      heatmapPlot: {
        selectedMetric: 'num_messages',
      },
      activePlotsTab: 'network',
    },

    /**
     * Save plot component UI state (axis selections, etc.)
     * @param {string} component - Component name (e.g., 'scatterPlot')
     * @param {Object} state - State object to merge with existing state
     */
    saveUIState(component, state) {
      this.uiState[component] = { ...this.uiState[component], ...state };
    },

    /**
     * Get plot component UI state
     * @param {string} component - Component name (e.g., 'scatterPlot')
     * @returns {Object} Component state object
     */
    getUIState(component) {
      return this.uiState[component] || {};
    },

    /**
     * Reset UI state for a specific component to defaults
     * @param {string} component - Component name to reset
     */
    resetUIState(component) {
      if (this.uiState[component]) {
        // Reset to initial defaults - could be enhanced to store defaults separately
        switch (component) {
          case 'scatterPlot':
            this.uiState[component] = {
              selectedXAxis: 'events_processed',
              selectedYAxis: 'events_rolled_back',
            };
            break;
          case 'timePlot':
            this.uiState[component] = {
              selectedXAxis: 'virtual_time',
              selectedYAxis: 'events_processed',
            };
            break;
          case 'networkTimePlot':
            this.uiState[component] = {
              selectedXAxis: 'virtual_time',
              selectedYAxis: 'send_count',
            };
            break;
          case 'heatmapPlot':
            this.uiState[component] = {
              selectedMetric: 'num_messages',
            };
            break;
          default:
            // Unknown component - no reset action needed
            break;
        }
      }
    },

    /**
     * Reset all UI state to defaults
     */
    resetAllUIState() {
      const components = ['scatterPlot', 'timePlot', 'networkTimePlot', 'heatmapPlot'];
      for (const component of components) {
        this.resetUIState(component);
      }
    },
  });
});
