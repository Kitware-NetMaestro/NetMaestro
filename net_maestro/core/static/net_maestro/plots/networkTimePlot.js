import Plotly from 'plotly.js-dist-min';

export const networkTimePlot = () => ({
  records: [],
  columns: [],
  selectedXAxis: 'virtual_time',
  selectedYAxis: 'send_count',
  minTime: null,
  maxTime: null,
  networkTimePlotEl: null,
  isPlotInitialized: false,
  isLoaded: false,

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
    this.$watch('$store.dataStore.loadTick', () => {
      this.load();
    });
  },

  /**
   * Initialize the Plotly time plot.
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
  },

  async load() {
    this.initPlot();
    await this.loadModelData();
  },

  async loadModelData() {
    const payload = await this.$store.dataStore.fetchModelData();
    this.columns = payload.columns ?? [];
    this.records = payload.data ?? [];
    this.updatePlotData();
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
