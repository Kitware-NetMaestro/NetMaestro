/**
 * Alpine.js component for time plot visualization.
 * Displays ROSS simulation data over time with configurable axes.
 */
import Plotly from 'plotly';

export const timePlot = () => ({
  records: [],
  columns: [],
  selectedXAxis: null,
  selectedYAxis: null,
  minTime: null,
  maxTime: null,
  timePlotEl: null,
  isPlotInitialized: false,
  isLoaded: false,
  noData: false,
  plotId: 'timePlot',
  isSyncing: false,

  get xAxisValues() {
    return [
      { key: 'virtual_time', label: 'Virtual Time' },
      { key: 'real_time', label: 'Real Time' },
    ];
  },
  get yAxisValues() {
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
   * Called automatically by Alpine.js when component mounts.
   */
  init() {
    // Restore UI state
    const savedState = this.$store.uiStateStore.getUIState('timePlot');
    this.selectedXAxis = savedState.selectedXAxis ?? 'virtual_time';
    this.selectedYAxis = savedState.selectedYAxis ?? 'events_processed';

    this.$watch('selectedXAxis', (newValue) => {
      if (newValue) {
        this.$store.uiStateStore.saveUIState('timePlot', { selectedXAxis: newValue });
      }
    });

    this.$watch('selectedYAxis', (newValue) => {
      if (newValue) {
        this.$store.uiStateStore.saveUIState('timePlot', { selectedYAxis: newValue });
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

    // Watch for range changes from other plots
    this.$watch('$store.plotSyncStore.parameterRanges', (ranges) => {
      if (sync.lastUpdatedBy === this.plotId) {
        return;
      }
      const xRange = ranges[this.selectedXAxis];
      const yRange = ranges[this.selectedYAxis];
      if (!xRange && !yRange) {
        return;
      }
      this.applySyncedRange(xRange, yRange);
    });

    // Watch for reset from other plots
    this.$watch('$store.plotSyncStore.resetTick', () => {
      if (sync.lastUpdatedBy === this.plotId || !this.isPlotInitialized) {
        return;
      }
      this.isSyncing = true;
      Plotly.relayout(this.timePlotEl, {
        'xaxis.autorange': true,
        'yaxis.autorange': true,
      }).finally(() => { this.isSyncing = false; });
    });
  },

  async applySyncedRange(xRange, yRange) {
    if (!this.timePlotEl || !this.isPlotInitialized) {
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
      await Plotly.relayout(this.timePlotEl, update);
    } finally {
      this.isSyncing = false;
    }
  },

  onRelayout(eventData) {
    if (this.isSyncing) {
      return;
    }
    const sync = this.$store.plotSyncStore;

    // Detect double-click reset
    if (eventData['xaxis.autorange'] || eventData['yaxis.autorange']) {
      sync.resetAll(this.plotId);
      return;
    }

    // Publish X-axis range
    if (eventData['xaxis.range[0]'] != null) {
      sync.updateRange(
        this.selectedXAxis,
        { min: eventData['xaxis.range[0]'], max: eventData['xaxis.range[1]'] },
        this.plotId,
      );
    }
    // Publish Y-axis range
    if (eventData['yaxis.range[0]'] != null) {
      sync.updateRange(
        this.selectedYAxis,
        { min: eventData['yaxis.range[0]'], max: eventData['yaxis.range[1]'] },
        this.plotId,
      );
    }
  },

  /**
   * Initialize the Plotly time plot.
   */
  initPlot() {
    if (this.isPlotInitialized) {
      return;
    }
    this.isPlotInitialized = true;
    this.timePlotEl = document.getElementById('timePlot');
    if (!this.timePlotEl) {
      return;
    }

    const data = [
      {
        x: [],
        y: [],
        showlegend: true,
      },
    ];
    const layout = {
      // biome-ignore-start lint/style/useNamingConvention: library interface names
      xaxis: {
        title: {
          text: 'Virtual Time',
        },
        rangemode: 'tozero',
        color: 'white',
      },
      yaxis: {
        title: {
          text: 'Events Processed',
        },
        rangemode: 'tozero',
        color: 'white',
      },
      paper_bgcolor: '1d232a',
      plot_bgcolor: '1d232a',
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
    Plotly.newPlot(this.timePlotEl, data, layout, config);

    this.timePlotEl.on('plotly_relayout', (eventData) => {
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
    this.columns = payload.columns ?? [];
    this.records = payload.data ?? [];
    if (this.records.length === 0) {
      this.noData = true;
      this.purge();
      return;
    }
    this.updatePlotData();
  },

  purge() {
    if (this.timePlotEl) {
      Plotly.purge(this.timePlotEl);
      this.isPlotInitialized = false;
    }
  },

  /**
   * Update the plot with current axis selections.
   * Groups data by PE_ID to create separate traces.
   */
  updatePlotData() {
    if (!this.timePlotEl || this.records.length === 0) {
      return;
    }

    const groupedData = {};

    for (const record of this.records) {
      const peId = record.PE_ID;
      if (!groupedData[peId]) {
        groupedData[peId] = {
          x: [],
          y: [],
          peId: peId,
        };
      }
      groupedData[peId].x.push(record[this.selectedXAxis]);
      groupedData[peId].y.push(record[this.selectedYAxis]);
    }

    const traces = Object.values(groupedData).map((peData) => ({
      x: peData.x,
      y: peData.y,
      showlegend: true,
    }));

    Plotly.react(this.timePlotEl, traces, {
      // biome-ignore-start lint/style/useNamingConvention: library interface names
      xaxis: {
        title: {
          text: this.xAxisValues.find((item) => item.key === this.selectedXAxis).label,
        },
        color: 'white',
      },
      yaxis: {
        title: {
          text: this.yAxisValues.find((item) => item.key === this.selectedYAxis).label,
        },
        color: 'white',
      },
      paper_bgcolor: '1d232a',
      plot_bgcolor: '1d232a',
      margin: {
        l: 50,
        r: 50,
        b: 50,
        t: 50,
        pad: 4,
      },
      // biome-ignore-end lint/style/useNamingConvention: library interface names
    });
  },
});
