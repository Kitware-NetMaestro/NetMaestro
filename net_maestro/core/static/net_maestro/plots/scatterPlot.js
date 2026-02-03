/**
 * Alpine.js component for scatter plot visualization.
 * Displays ROSS simulation data as a scatter plot with configurable axes.
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('scatterPlot', () => ({
    // Component state
    records: [],
    columns: [],
    valueList: [],
    selectedXAxis: 'events_processed',
    selectedYAxis: 'events_rolled_back',
    scatterPlotEl: null,
    resizeObserver: null,
    isPlotInitialized: false,
    isLoaded: false,

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

        const data = [{
            x: [],
            y: [],
            mode: 'markers',
            type: 'scatter',
            showlegend: true,
        }];
        const layout = {
            xaxis: {
                title: {
                    text: 'Events Processed'
                },
                rangemode: 'tozero',
                color: 'white',
            },
            yaxis: {
                title: {
                    text: 'Events Rolled Back'
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
                pad: 4
            }
        };
        const config = { responsive: true };
        Plotly.newPlot(this.scatterPlotEl, data, layout, config);

        this.setupResizeObserver();
    },

    async load() {
        this.initPlot();
        await this.loadRossData();
        this.isLoaded = true;
        this.resizePlot();
    },

    setupResizeObserver() {
        if (!this.scatterPlotEl) {
            return;
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        this.resizeObserver = new ResizeObserver(() => {
            this.resizePlot();
        });
        this.resizeObserver.observe(this.scatterPlotEl);
    },

    resizePlot() {
        if (!this.scatterPlotEl) {
            return;
        }
        requestAnimationFrame(() => {
            Plotly.Plots.resize(this.scatterPlotEl);
        });
    },

    async loadRossData() {
        this.isLoaded = false;
        const payload = await this.$store.dataStore.fetchRossData();
        this.columns = payload.columns ?? [];
        this.records = payload.data ?? [];
        this.processData();
        this.updatePlotData();
    },

    /**
     * Process raw data to create axis value options.
     */
    processData() {
        const excluded_columns = ["PE_ID", "real_time", "virtual_time"];
        const filtered_columns = this.columns.filter(column => column && !excluded_columns.includes(column));
        this.valueList = filtered_columns.map((value) => ({
            key: value,
            label: value.replaceAll("_", " ")
        }));
    },

    /**
     * Update the plot with current axis selections.
     */
    updatePlotData() {
        if (!this.scatterPlotEl || this.records.length === 0) {
            return;
        }

        const xData = this.records.map(record => record[this.selectedXAxis]);
        const yData = this.records.map(record => record[this.selectedYAxis]);

        // TODO: This could be another choice we allow the user to make.
        const color_range = this.records.map(record => record.PE_ID);

        Plotly.update(this.scatterPlotEl, {
            x: [xData],
            y: [yData],
            marker: {
                color: color_range,
                colorscale: 'Blues'
            }
        }, {
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
            }
        });
    }
    }));
});
