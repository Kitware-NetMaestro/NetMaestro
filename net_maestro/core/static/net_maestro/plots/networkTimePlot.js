import Plotly from 'plotly';
import {
  axisConfig,
  createValueList,
  DARK_LAYOUT,
  getLabel,
  initPlot,
  purgePlot,
  setupAxisState,
  setupLoadWatcher,
} from './plotUtils.js';

export const networkTimePlot = () => ({
  records: [],
  columns: [],
  selectedXAxis: null,
  selectedYAxis: null,
  networkTimePlotEl: null,
  isPlotInitialized: false,
  isLoaded: false,
  noData: false,

  get xAxisValues() {
    return [
      { key: 'virtual_time', label: 'Virtual Time' },
      { key: 'real_time', label: 'Real Time' },
    ];
  },
  get yAxisValues() {
    return createValueList(this.columns, ['lp_id', 'component_id', 'real_time', 'virtual_time']);
  },

  /**
   * Initialize the component and set up watchers.
   * Called automatically by Alpine.js when component mounts.
   */
  init() {
    setupAxisState(this, 'networkTimePlot', [
      { prop: 'selectedXAxis', default: 'virtual_time' },
      { prop: 'selectedYAxis', default: 'send_count' },
    ]);
    setupLoadWatcher(this, () => this.load());
  },

  /**
   * Initialize the Plotly networkTime plot.
   */
  initPlot() {
    const layout = {
      ...DARK_LAYOUT,
      xaxis: axisConfig('Virtual Time', { rangemode: 'tozero' }),
      yaxis: axisConfig('Send Count', { rangemode: 'tozero' }),
    };
    const data = [{ x: [], y: [], showlegend: true }];
    initPlot({
      component: this,
      elementId: 'networkTimePlot',
      elementProp: 'networkTimePlotEl',
      data,
      layout,
    });
  },

  async load() {
    this.initPlot();
    await this.loadModelData();
  },

  async loadModelData() {
    this.noData = false;
    const payload = await this.$store.dataStore.fetchModelData();
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
    purgePlot(this, 'networkTimePlotEl');
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
      ...DARK_LAYOUT,
      xaxis: axisConfig(getLabel(this.xAxisValues, this.selectedXAxis, this.selectedXAxis)),
      yaxis: axisConfig(getLabel(this.yAxisValues, this.selectedYAxis, this.selectedYAxis)),
    });
  },
});
