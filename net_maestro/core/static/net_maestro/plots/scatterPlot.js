/**
 * Alpine.js component for scatter plot visualization.
 * Displays ROSS simulation data as a scatter plot with configurable axes.
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
    return createValueList(this.columns, ['PE_ID', 'real_time', 'virtual_time']);
  },

  /**
   * Initialize the component and set up watchers.
   */
  init() {
    setupAxisState(this, 'scatterPlot', [
      { prop: 'selectedXAxis', default: 'events_processed' },
      { prop: 'selectedYAxis', default: 'events_rolled_back' },
    ]);
    setupLoadWatcher(this, () => this.load());
    setupXYSyncWatchers(
      this,
      'scatterPlotEl',
      () => this.selectedXAxis,
      () => this.selectedYAxis,
    );
  },

  /**
   * Initialize the Plotly scatter plot.
   */
  initPlot() {
    const layout = {
      ...DARK_LAYOUT,
      xaxis: axisConfig('Events Processed'),
      yaxis: axisConfig('Events Rolled Back'),
    };
    const data = [{ x: [], y: [], mode: 'markers', type: 'scatter', showlegend: true }];
    setupPlot({
      component: this,
      elementId: 'scatterPlot',
      elementProp: 'scatterPlotEl',
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
    purgePlot(this, 'scatterPlotEl');
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
        xaxis: axisConfig(getLabel(this.valueList, this.selectedXAxis, this.selectedXAxis)),
        yaxis: axisConfig(getLabel(this.valueList, this.selectedYAxis, this.selectedYAxis)),
      },
    );
  },
});
