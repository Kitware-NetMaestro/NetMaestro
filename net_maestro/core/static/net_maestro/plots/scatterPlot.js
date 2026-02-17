/**
 * Alpine.js component for scatter plot visualization.
 * Displays ROSS simulation data as a scatter plot with configurable axes.
 */
import Plotly from 'plotly.js-dist-min';

export const scatterPlot = () => ({
  // Component state
  records: [],
  columns: [],
  selectedXAxis: 'events_processed',
  selectedYAxis: 'events_rolled_back',
  scatterPlotEl: null,
  isPlotInitialized: false,
  isLoaded: false,

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
    this.isPlotInitialized = true;
    this.scatterPlotEl = document.getElementById('scatterPlot');

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
    Plotly.newPlot(this.scatterPlotEl, data, layout, config);
  },

  async load() {
    this.initPlot();
    await this.loadRossData();
    this.isLoaded = true;
  },

  async loadRossData() {
    this.isLoaded = false;
    const payload = await this.$store.dataStore.fetchRossData();
    this.columns = payload.columns ?? [];
    this.records = payload.data ?? [];
    this.updatePlotData();
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
            text: this.valueList.find((item) => item.key === this.selectedXAxis).label,
          },
          color: 'white',
        },
        yaxis: {
          title: {
            text: this.valueList.find((item) => item.key === this.selectedYAxis).label,
          },
          color: 'white',
        },
      },
    );
  },
});
