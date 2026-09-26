/**
 * Alpine.js component for time plot visualization.
 * Displays ROSS simulation data over time with configurable axes.
 */
import Plotly from 'plotly';
import { plotProfileFor } from './plotProfiles.js';
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

  get profile() {
    return plotProfileFor(this.$store.dataStore.simulationType).simulation;
  },

  get xAxisValues() {
    return this.profile.timeAxes;
  },
  get yAxisValues() {
    return createValueList(this.columns, this.profile.excludedColumns);
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
    const payload = await this.$store.dataStore.fetchRunData(this.profile.dataset);
    this.columns = payload?.columns ?? [];
    this.records = payload?.data ?? [];
    // Saved axes may belong to another simulation type; fall back to this type's defaults.
    if (this.columns.length > 0 && !this.columns.includes(this.selectedXAxis)) {
      this.selectedXAxis = this.profile.timeDefaults.x;
    }
    if (this.columns.length > 0 && !this.columns.includes(this.selectedYAxis)) {
      this.selectedYAxis = this.profile.timeDefaults.y;
    }
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
      const seriesId = record[this.profile.groupBy];
      if (!groupedData[seriesId]) {
        groupedData[seriesId] = {
          x: [],
          y: [],
          seriesId: seriesId,
        };
      }
      groupedData[seriesId].x.push(record[this.selectedXAxis]);
      groupedData[seriesId].y.push(record[this.selectedYAxis]);
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
