/**
 * Alpine.js component for time plot visualization.
 * Displays ROSS simulation data over time with configurable axes.
 */
import Plotly from 'plotly';
import {
  axisConfig,
  createValueList,
  DARK_LAYOUT,
  getLabel,
  handleRelayout,
  purgePlot,
  setupAxisState,
  setupLoadWatcher,
  setupPlot,
  setupXYSyncWatchers,
} from './plotUtils.js';

export const timePlot = () => ({
  records: [],
  columns: [],
  selectedXAxis: null,
  selectedYAxis: null,
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
    return createValueList(this.columns, ['PE_ID', 'real_time', 'virtual_time']);
  },

  /**
   * Initialize the component and set up watchers.
   * Called automatically by Alpine.js when component mounts.
   */
  init() {
    setupAxisState(this, 'timePlot', [
      { prop: 'selectedXAxis', default: 'virtual_time' },
      { prop: 'selectedYAxis', default: 'events_processed' },
    ]);
    setupLoadWatcher(this, () => this.load());
    setupXYSyncWatchers(
      this,
      'timePlotEl',
      () => this.selectedXAxis,
      () => this.selectedYAxis,
    );
  },

  /**
   * Initialize the Plotly time plot.
   */
  initPlot() {
    const layout = {
      ...DARK_LAYOUT,
      xaxis: axisConfig('Virtual Time', { rangemode: 'tozero' }),
      yaxis: axisConfig('Events Processed', { rangemode: 'tozero' }),
    };
    const data = [{ x: [], y: [], showlegend: true }];
    setupPlot({
      component: this,
      elementId: 'timePlot',
      elementProp: 'timePlotEl',
      data,
      layout,
      eventHandlers: [
        {
          event: 'plotly_relayout',
          handler: (eventData) =>
            handleRelayout(
              this,
              eventData,
              () => this.selectedXAxis,
              () => this.selectedYAxis,
            ),
        },
      ],
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
    purgePlot(this, 'timePlotEl');
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
      ...DARK_LAYOUT,
      xaxis: axisConfig(getLabel(this.xAxisValues, this.selectedXAxis, this.selectedXAxis)),
      yaxis: axisConfig(getLabel(this.yAxisValues, this.selectedYAxis, this.selectedYAxis)),
    });
  },
});
