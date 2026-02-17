/**
 * Alpine.js component for time plot visualization.
 * Displays ROSS simulation data over time with configurable axes.
 */

document.addEventListener('alpine:init', () => {
  Alpine.data('timePlot', () => ({
    records: [],
    columns: [],
    selectedXAxis: 'virtual_time',
    selectedYAxis: 'events_processed',
    minTime: null,
    maxTime: null,
    timePlotEl: null,
    isPlotInitialized: false,
    isLoaded: false,

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
  }));
});
