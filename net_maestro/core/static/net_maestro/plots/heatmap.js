/**
 * Alpine.js component for scatter plot visualization.
 * Displays ROSS simulation data as a scatter plot with configurable axes.
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('heatmapPlot', () => ({
    heatmapPlotEl: null,
    isPlotInitialized: false,
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
    selectedMetric: 'num_messages',

    /**
     * Initialize the component and set up watchers.
     */
    init() {
      this.$watch('$store.dataStore.loadTick', () => {
        this.load();
      });
    },

    /**
     * Initialize the Plotly scatter plot.
     */
    initPlot() {
      if (this.isPlotInitialized) {
        return;
      }
      this.heatmapPlotEl = document.getElementById('heatmapPlot');

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
        xaxis: {
          title: 'Receiving LP ID',
        },
        yaxis: {
          title: 'Sending LP ID',
        },
      };
      const config = { responsive: true };
      Plotly.newPlot(this.heatmapPlotEl, data, layout, config);
    },

    async load() {
      this.initPlot();
      await this.loadEventData();
      this.isPlotInitialized = true;
    },

    async loadEventData() {
      const payload = await this.$store.dataStore.fetchEventData();
      this.records = payload.data ?? [];
      this.updatePlotData();
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
  }));
});
