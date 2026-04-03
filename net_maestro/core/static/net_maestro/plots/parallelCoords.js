/**
 * Alpine.js component for parallel coordinates plot visualization.
 * Displays multi-dimensional ROSS data using Plotly's parallel coordinates chart.
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('parallelCoords', () => ({
    parallelPlotEl: null,
    isPlotInitialized: false,
    noData: false,
    plotId: 'parallelCoords',
    isSyncing: false,
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
      // Load cached data if available
      if (this.$store.dataStore.rossDataCache) {
        this.load();
      }

      // Watch for new data loads
      this.$watch('$store.dataStore.loadTick', () => {
        this.load();
      });

      this.setupSyncWatchers();
    },

    setupSyncWatchers() {
      const sync = this.$store.plotSyncStore;

      this.$watch('$store.plotSyncStore.parameterRanges', (ranges) => {
        if (sync.lastUpdatedBy === this.plotId || !this.isPlotInitialized) {
          return;
        }
        for (let i = 0; i < this.plotDimensions.length; i++) {
          const dimKey = this.plotDimensions[i].key;
          const range = ranges[dimKey];
          if (range) {
            this.applySyncedDimension(i, [range.min, range.max]);
          }
        }
      });

      this.$watch('$store.plotSyncStore.resetTick', () => {
        if (sync.lastUpdatedBy === this.plotId || !this.isPlotInitialized) {
          return;
        }
        this.resetAllDimensions();
      });
    },

    applySyncedDimension(index, constraintRange) {
      if (!this.parallelPlotEl) {
        return;
      }
      this.isSyncing = true;
      const dimensions = this.parallelPlotEl.data[0]?.dimensions;
      if (dimensions && dimensions[index]) {
        dimensions[index].constraintrange = constraintRange;
        Plotly.restyle(this.parallelPlotEl, { dimensions: [dimensions] })
          .then(() => { this.isSyncing = false; });
      } else {
        this.isSyncing = false;
      }
    },

    resetAllDimensions() {
      if (!this.parallelPlotEl) {
        return;
      }
      this.isSyncing = true;
      const dimensions = this.parallelPlotEl.data[0]?.dimensions;
      if (dimensions) {
        for (const dim of dimensions) {
          delete dim.constraintrange;
          delete dim.range;
        }
        Plotly.restyle(this.parallelPlotEl, { dimensions: [dimensions] })
          .then(() => { this.isSyncing = false; });
      } else {
        this.isSyncing = false;
      }
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
