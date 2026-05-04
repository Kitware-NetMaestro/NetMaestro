/**
 * Alpine.js component for scatter plot visualization.
 * Displays ROSS simulation data as a scatter plot with configurable axes.
 */
import Plotly from 'plotly';

export const scatterPlot = () => ({
  // Component state
  records: [],
  columns: [],
  selectedXAxis: null,
  selectedYAxis: null,
  scatterPlotEl: null,
  isPlotInitialized: false,
  isLoaded: false,
  noData: false,
  plotId: 'scatterPlot',
  isSyncing: false,

  get valueList() {
    const excludedColumns = ['PE_ID', 'real_time', 'virtual_time'];
    const filteredColumns = this.columns.filter(
      (column) => column && !excludedColumns.includes(column),
    );
    return filteredColumns.map((value) => ({
      key: value,
      label: value.replaceAll('_', ' '),
    }));
  },

  /**
   * Initialize the component and set up watchers.
   */
  init() {
    // Restore UI state
    const savedState = this.$store.uiStateStore.getUIState('scatterPlot');
    this.selectedXAxis = savedState.selectedXAxis ?? 'events_processed';
    this.selectedYAxis = savedState.selectedYAxis ?? 'events_rolled_back';

    this.$watch('selectedXAxis', (newValue) => {
      if (newValue) {
        this.$store.uiStateStore.saveUIState('scatterPlot', { selectedXAxis: newValue });
      }
    });

    this.$watch('selectedYAxis', (newValue) => {
      if (newValue) {
        this.$store.uiStateStore.saveUIState('scatterPlot', { selectedYAxis: newValue });
      }
    });

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
      if (sync.lastUpdatedBy === this.plotId) {
        return;
      }
      const xRange = ranges[this.selectedXAxis];
      const yRange = ranges[this.selectedYAxis];
      if (!(xRange || yRange)) {
        return;
      }
      this.applySyncedRange(xRange, yRange);
    });

    this.$watch('$store.plotSyncStore.resetTick', async () => {
      if (sync.lastUpdatedBy === this.plotId || !this.isPlotInitialized) {
        return;
      }
      this.isSyncing = true;
      try {
        await Plotly.relayout(this.scatterPlotEl, {
          'xaxis.autorange': true,
          'yaxis.autorange': true,
        });
      } finally {
        this.isSyncing = false;
      }
    });
  },

  async applySyncedRange(xRange, yRange) {
    if (!(this.scatterPlotEl && this.isPlotInitialized)) {
      return;
    }
    const update = {};
    if (xRange) {
      update['xaxis.range'] = [xRange.min, xRange.max];
    }
    if (yRange) {
      update['yaxis.range'] = [yRange.min, yRange.max];
    }
    if (Object.keys(update).length === 0) {
      return;
    }
    this.isSyncing = true;
    try {
      await Plotly.relayout(this.scatterPlotEl, update);
    } finally {
      this.isSyncing = false;
    }
  },

  onRelayout(eventData) {
    if (this.isSyncing) {
      return;
    }
    const sync = this.$store.plotSyncStore;

    if (eventData['xaxis.autorange'] || eventData['yaxis.autorange']) {
      sync.resetAll(this.plotId);
      return;
    }

    const updates = this.collectRangeUpdates(eventData);
    if (updates.length > 0) {
      sync.updateRanges(updates, this.plotId);
    }
  },

  collectRangeUpdates(eventData) {
    const updates = [];
    if (eventData['xaxis.range[0]'] != null) {
      updates.push({
        parameter: this.selectedXAxis,
        range: { min: eventData['xaxis.range[0]'], max: eventData['xaxis.range[1]'] },
      });
    }
    if (eventData['yaxis.range[0]'] != null) {
      updates.push({
        parameter: this.selectedYAxis,
        range: { min: eventData['yaxis.range[0]'], max: eventData['yaxis.range[1]'] },
      });
    }
    return updates;
  },

  /**
   * Initialize the Plotly scatter plot.
   */
  initPlot() {
    if (this.isPlotInitialized) {
      return;
    }
    this.scatterPlotEl = document.getElementById('scatterPlot');
    if (!this.scatterPlotEl) {
      return;
    }

    const data = [
      {
        x: [],
        y: [],
        mode: 'markers',
        type: 'scatter',
        showlegend: true,
      },
    ];
    const layout = {
      // biome-ignore-start lint/style/useNamingConvention: library interface names
      xaxis: {
        title: {
          text: 'Events Processed',
        },
        rangemode: 'tozero',
        color: 'white',
      },
      yaxis: {
        title: {
          text: 'Events Rolled Back',
        },
        rangemode: 'tozero',
        color: 'white',
      },
      paper_bgcolor: '#1d232a',
      plot_bgcolor: '#1d232a',
      margin: {
        l: 50,
        r: 50,
        b: 50,
        t: 50,
        pad: 4,
      },
      // biome-ignore-end lint/style/useNamingConvention: library interface names
    };
    const config = { responsive: true };
    Plotly.newPlot(this.scatterPlotEl, data, layout, config);
    this.isPlotInitialized = true;

    this.scatterPlotEl.on('plotly_relayout', (eventData) => {
      this.onRelayout(eventData);
    });
  },

  async load() {
    this.initPlot();
    await this.loadRossData();
    this.isLoaded = true;
  },

  async loadRossData() {
    this.isLoaded = false;
    this.noData = false;
    const payload = await this.$store.dataStore.fetchRossData();
    this.columns = payload?.columns ?? [];
    this.records = payload?.data ?? [];
    if (this.records.length === 0) {
      this.noData = true;
      this.purge();
      return;
    }
    this.updatePlotData();
  },

  purge() {
    if (this.scatterPlotEl) {
      Plotly.purge(this.scatterPlotEl);
      this.isPlotInitialized = false;
    }
  },

  /**
   * Update the plot with current axis selections.
   */
  updatePlotData() {
    if (!this.scatterPlotEl || this.records.length === 0) {
      return;
    }

    const xData = this.records.map((record) => record[this.selectedXAxis]);
    const yData = this.records.map((record) => record[this.selectedYAxis]);

    // TODO: This could be another choice we allow the user to make.
    const colorRange = this.records.map((record) => record.PE_ID);

    Plotly.update(
      this.scatterPlotEl,
      {
        x: [xData],
        y: [yData],
        marker: {
          color: colorRange,
          colorscale: 'Blues',
        },
      },
      {
        xaxis: {
          title: {
            text:
              this.valueList.find((item) => item.key === this.selectedXAxis)?.label ??
              this.selectedXAxis,
          },
          color: 'white',
        },
        yaxis: {
          title: {
            text:
              this.valueList.find((item) => item.key === this.selectedYAxis)?.label ??
              this.selectedYAxis,
          },
          color: 'white',
        },
      },
    );
  },
});
