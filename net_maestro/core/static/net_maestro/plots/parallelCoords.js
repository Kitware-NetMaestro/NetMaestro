/**
 * Alpine.js component for parallel coordinates plot visualization.
 * Displays multi-dimensional ROSS data using Plotly's parallel coordinates chart.
 */
import Plotly from 'plotly';

export const parallelCoords = () => ({
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
    // Load data if a run is already selected
    if (this.$store.dataStore.selectedRunId) {
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

  async applySyncedDimension(index, constraintRange) {
    if (!this.parallelPlotEl) {
      return;
    }
    this.isSyncing = true;
    const dimensions = this.parallelPlotEl.data[0]?.dimensions;
    if (dimensions?.[index]) {
      dimensions[index].constraintrange = constraintRange;
      try {
        await Plotly.restyle(this.parallelPlotEl, { dimensions: [dimensions] });
      } finally {
        this.isSyncing = false;
      }
    } else {
      this.isSyncing = false;
    }
  },

  async resetAllDimensions() {
    if (!this.parallelPlotEl) {
      return;
    }
    this.isSyncing = true;
    const dimensions = this.parallelPlotEl.data[0]?.dimensions;
    if (dimensions) {
      for (const dim of dimensions) {
        dim.constraintrange = undefined;
        dim.range = undefined;
      }
      try {
        await Plotly.restyle(this.parallelPlotEl, { dimensions: [dimensions] });
      } finally {
        this.isSyncing = false;
      }
    } else {
      this.isSyncing = false;
    }
  },

  /**
   * Handle user constraint range changes on dimensions.
   * Publishes the current constraint state to plotSyncStore.
   */
  onRestyle() {
    if (this.isSyncing) {
      return;
    }
    const sync = this.$store.plotSyncStore;
    const dimensions = this.parallelPlotEl.data[0]?.dimensions;
    if (!dimensions) {
      return;
    }

    const updates = this.plotDimensions.map((dim, i) => {
      const constraint = dimensions[i]?.constraintrange;
      return {
        parameter: dim.key,
        range: constraint ? { min: constraint[0], max: constraint[1] } : null,
      };
    });

    if (updates.every((u) => u.range === null)) {
      sync.resetAll(this.plotId);
      return;
    }
    sync.updateRanges(updates, this.plotId);
  },

  /**
   * Initialize the Plotly parallel coordinates plot.
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
      paper_bgcolor: '#1d232a',
      plot_bgcolor: '#1d232a',
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

    this.parallelPlotEl.on('plotly_restyle', () => {
      this.onRestyle();
    });
  },

  async load() {
    this.initPlot();
    await this.loadRossData();
  },

  async loadRossData() {
    this.noData = false;
    const payload = await this.$store.dataStore.fetchRossData();
    this.records = payload?.data ?? [];
    if (this.records.length === 0) {
      this.noData = true;
      this.purge();
      return;
    }
    this.updatePlotData();
  },

  purge() {
    if (this.parallelPlotEl) {
      Plotly.purge(this.parallelPlotEl);
      this.isPlotInitialized = false;
    }
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
      paper_bgcolor: '#1d232a',
      plot_bgcolor: '#1d232a',
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
});
