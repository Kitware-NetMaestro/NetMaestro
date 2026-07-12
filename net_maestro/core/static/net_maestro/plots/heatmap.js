/**
 * Alpine.js component for heatmap visualization.
 * Displays event communication patterns between LPs as a heatmap.
 */
import _ from 'lodash';
import Plotly from 'plotly';
import {
  DARK_LAYOUT,
  purgePlot,
  setupAxisState,
  setupLoadWatcher,
  setupPlot,
} from './plotUtils.js';

export const heatmapPlot = () => ({
  heatmapPlotEl: null,
  isPlotInitialized: false,
  noData: false,
  records: [],
  metricList: [
    { key: 'num_messages', label: 'Num Messages', disabled: false },
    {
      key: 'bytes_sent',
      label: 'Bytes Sent (not available)',
      disabled: true,
      tooltip: 'Message size data not available in current event trace format',
    },
  ],
  selectedMetric: null,

  /**
   * Initialize the component and set up watchers.
   */
  init() {
    setupAxisState(this, 'heatmapPlot', [{ prop: 'selectedMetric', default: 'num_messages' }]);
    setupLoadWatcher(this, () => this.load());
  },

  /**
   * Initialize the Plotly heatmap plot.
   */
  initPlot() {
    const data = [
      {
        type: 'heatmap',
        z: [],
        x: [],
        y: [],
        colorscale: 'Viridis',
      },
    ];
    const layout = {
      ...DARK_LAYOUT,
      xaxis: {
        title: 'Receiving LP ID',
      },
      yaxis: {
        title: 'Sending LP ID',
      },
    };
    setupPlot({
      component: this,
      elementId: 'heatmapPlot',
      elementProp: 'heatmapPlotEl',
      data,
      layout,
    });
  },

  async load() {
    this.initPlot();
    await this.loadEventData();
  },

  async loadEventData() {
    this.noData = false;
    const payload = await this.$store.dataStore.fetchEventData();
    this.records = payload?.data ?? [];
    if (this.records.length === 0) {
      this.noData = true;
      this.purge();
      return;
    }
    this.updatePlotData();
  },

  purge() {
    purgePlot(this, 'heatmapPlotEl');
  },

  createHeatmapMatrix() {
    if (this.records.length === 0) {
      return null;
    }

    const sortedSources = _(this.records)
      .map('source_lp')
      .reject(_.isUndefined)
      .uniq()
      .sortBy()
      .value();
    const sortedDests = _(this.records)
      .map('dest_lp')
      .reject(_.isUndefined)
      .uniq()
      .sortBy()
      .value();
    const counts = _.countBy(this.records, (record) => `${record.source_lp}_${record.dest_lp}`);

    const z = sortedSources.map((source) =>
      sortedDests.map((dest) => counts[`${source}_${dest}`] ?? 0),
    );

    return {
      z,
      x: sortedDests,
      y: sortedSources,
    };
  },

  updatePlotData() {
    if (!this.heatmapPlotEl || this.records.length === 0) {
      return;
    }

    const matrix = this.createHeatmapMatrix();
    if (!matrix) {
      return;
    }

    const title =
      this.metricList.find((m) => m.key === this.selectedMetric)?.label || this.selectedMetric;
    Plotly.react(
      this.heatmapPlotEl,
      [
        {
          type: 'heatmap',
          z: matrix.z,
          x: matrix.x,
          y: matrix.y,
          colorscale: 'Viridis',
        },
      ],
      {
        ...DARK_LAYOUT,
        xaxis: {
          title: 'Receiving LP ID',
        },
        yaxis: {
          title: 'Sending LP ID',
        },
        coloraxis: {
          colorbar: { title: title },
        },
      },
    );
  },
});
