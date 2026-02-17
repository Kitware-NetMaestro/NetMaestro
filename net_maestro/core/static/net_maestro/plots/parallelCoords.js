/**
 * Alpine.js component for parallel coordinates plot visualization.
 * Displays multi-dimensional ROSS data using Plotly's parallel coordinates chart.
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('parallelCoords', () => ({
    parallelPlotEl: null,
    isPlotInitialized: false,
    records: [],
    plotDimensions: [
      { key: 'PE_ID', label: 'PE ID' },
      { key: 'events_processed', label: 'Events Processed' },
      { key: 'events_rolled_back', label: 'Events Rolled Back' },
      { key: 'total_rollbacks', label: 'Total Rollbacks' },
      { key: 'secondary_rollbacks', label: 'Secondary Rollbacks' },
    ],

    /**
     * Initialize the component and set up watchers.
     */
    init() {
      this.$watch('$store.dataStore.loadTick', () => {
        this.load();
      });
    },

    /**
     * Initialize the Plotly scatter plot.
     */
    initPlot() {
      if (this.isPlotInitialized) {
        return;
      }
      this.parallelPlotEl = document.getElementById('parallelCoords');

      const data = [
        {
          type: 'parcoords',
          line: {
            color: [],
            colorscale: 'Viridis',
            showscale: true,
          },
          dimensions: [{}],
        },
      ];
      const layout = {
        // biome-ignore-start lint/style/useNamingConvention: library interface names
        paper_bgcolor: '1d232a',
        plot_bgcolor: '1d232a',
        font: {
          color: 'white',
        },
        margin: {
          t: 50,
          b: 50,
          l: 50,
          r: 50,
          pad: 4,
        },
        // biome-ignore-end lint/style/useNamingConvention: library interface names
      };
      const config = { responsive: true };
      Plotly.newPlot(this.parallelPlotEl, data, layout, config);

      this.isPlotInitialized = true;
    },

    async load() {
      this.initPlot();
      await this.loadRossData();
    },

    async loadRossData() {
      const payload = await this.$store.dataStore.fetchRossData();
      this.records = payload.data ?? [];
      this.updatePlotData();
    },

    /**
     * Update the plot with current axis selections.
     */
    updatePlotData() {
      if (!this.parallelPlotEl || this.records.length === 0) {
        return;
      }

      const trace = {
        type: 'parcoords',
        line: {
          color: this.records.map((record) => record.PE_ID),
          colorscale: 'Viridis',
          showscale: true,
        },
        dimensions: this.plotDimensions.map((dimension) => ({
          label: dimension.label,
          values: this.records.map((record) => record[dimension.key]),
        })),
      };

      const layout = {
        // biome-ignore-start lint/style/useNamingConvention: library interface names
        paper_bgcolor: '1d232a',
        plot_bgcolor: '1d232a',
        font: {
          color: 'white',
        },
        margin: {
          t: 50,
          b: 50,
          l: 50,
          r: 50,
          pad: 4,
        },
        // biome-ignore-end lint/style/useNamingConvention: library interface names
      };

      Plotly.react(this.parallelPlotEl, [trace], layout);
    },
  }));
});
