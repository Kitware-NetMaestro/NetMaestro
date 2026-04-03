import Plotly from 'plotly';

export const networkTimePlot = () => ({
  records: [],
  columns: [],
  selectedXAxis: null,
  selectedYAxis: null,
  minTime: null,
  maxTime: null,
  networkTimePlotEl: null,
  isPlotInitialized: false,
  isLoaded: false,
  noData: false,
  plotId: 'networkTimePlot',
  isSyncing: false,

  get xAxisValues() {
    return [
      { key: 'virtual_time', label: 'Virtual Time' },
      { key: 'real_time', label: 'Real Time' },
    ];
  },
  get yAxisValues() {
    const excludedColumns = ['lp_id', 'component_id', 'real_time', 'virtual_time'];
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
    const savedState = this.$store.uiStateStore.getUIState('networkTimePlot');
    this.selectedXAxis = savedState.selectedXAxis ?? 'virtual_time';
    this.selectedYAxis = savedState.selectedYAxis ?? 'send_count';

    this.$watch('selectedXAxis', (newValue) => {
      if (newValue) {
        this.$store.uiStateStore.saveUIState('networkTimePlot', { selectedXAxis: newValue });
      }
    });

    this.$watch('selectedYAxis', (newValue) => {
      if (newValue) {
        this.$store.uiStateStore.saveUIState('networkTimePlot', { selectedYAxis: newValue });
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
      if (!xRange && !yRange) {
        return;
      }
      this.applySyncedRange(xRange, yRange);
    });

    this.$watch('$store.plotSyncStore.resetTick', () => {
      if (sync.lastUpdatedBy === this.plotId || !this.isPlotInitialized) {
        return;
      }
      this.isSyncing = true;
      Plotly.relayout(this.networkTimePlotEl, {
        'xaxis.autorange': true,
        'yaxis.autorange': true,
      }).finally(() => { this.isSyncing = false; });
    });
  },

  async applySyncedRange(xRange, yRange) {
    if (!this.networkTimePlotEl || !this.isPlotInitialized) {
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
      await Plotly.relayout(this.networkTimePlotEl, update);
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

    if (eventData['xaxis.range[0]'] != null) {
      sync.updateRange(
        this.selectedXAxis,
        { min: eventData['xaxis.range[0]'], max: eventData['xaxis.range[1]'] },
        this.plotId,
      );
    }
    if (eventData['yaxis.range[0]'] != null) {
      sync.updateRange(
        this.selectedYAxis,
        { min: eventData['yaxis.range[0]'], max: eventData['yaxis.range[1]'] },
        this.plotId,
      );
    }
  },

  /**
   * Initialize the Plotly networkTime plot.
   */
  initPlot() {
    if (this.isPlotInitialized) {
      return;
    }
    this.networkTimePlotEl = document.getElementById('networkTimePlot');
    if (!this.networkTimePlotEl) {
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
          text: 'Send Count',
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
    Plotly.newPlot(this.networkTimePlotEl, data, layout, config);
    this.isPlotInitialized = true;

    this.networkTimePlotEl.on('plotly_relayout', (eventData) => {
      this.onRelayout(eventData);
    });
  },

  async load() {
    this.initPlot();
    await this.loadModelData();
  },

  async loadModelData() {
    this.noData = false;
    const payload = await this.$store.dataStore.fetchModelData();
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
    if (this.networkTimePlotEl) {
      Plotly.purge(this.networkTimePlotEl);
      this.isPlotInitialized = false;
    }
  },

  /**
   * Update the plot with current axis selections.
   * Groups data by lp_id to create separate traces.
   */
  updatePlotData() {
    if (!(this.networkTimePlotEl && this.records.length)) {
      return;
    }

    const groupedData = {};

    for (const record of this.records) {
      const lpId = record.lp_id;
      if (!groupedData[lpId]) {
        groupedData[lpId] = {
          x: [],
          y: [],
          lpId: lpId,
        };
      }

      groupedData[lpId].x.push(record[this.selectedXAxis]);
      groupedData[lpId].y.push(record[this.selectedYAxis]);
    }

    const traces = Object.values(groupedData).map((lpData) => ({
      x: lpData.x,
      y: lpData.y,
      showlegend: true,
    }));

    Plotly.react(this.networkTimePlotEl, traces, {
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
