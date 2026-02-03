/**
 * Alpine.js component for time plot visualization.
 * Displays ROSS simulation data over time with configurable axes.
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('timePlot', () => ({
    // Component state
    records: [],
    columns: [],
    xAxisValues: [
        {
            key: "virtual_time",
            label: "Virtual Time"
        },
        {
            key: "real_time",
            label: "Real Time"
        },
    ],
    yAxisValues: [],
    selectedXAxis: 'virtual_time',
    selectedYAxis: 'events_processed',
    minTime: null,
    maxTime: null,
    timePlotEl: null,
    resizeObserver: null,
    isPlotInitialized: false,
    isLoaded: false,

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

        const data = [{
            x: [],
            y: [],
            showlegend: true,
        }];
        const layout = {
            xaxis: {
                title: {
                    text: 'Virtual Time'
                },
                rangemode: 'tozero',
                color: 'white',
            },
            yaxis: {
                title: {
                    text: 'Events Processed'
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
        Plotly.newPlot(this.timePlotEl, data, layout, config);

        this.setupResizeObserver();
    },

    async load() {
        this.initPlot();
        await this.loadRossData();
        this.isLoaded = true;
        this.resizePlot();
    },

    setupResizeObserver() {
        if (!this.timePlotEl) {
            return;
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        this.resizeObserver = new ResizeObserver(() => {
            this.resizePlot();
        });
        this.resizeObserver.observe(this.timePlotEl);
    },

    resizePlot() {
        if (!this.timePlotEl) {
            return;
        }
        requestAnimationFrame(() => {
            Plotly.Plots.resize(this.timePlotEl);
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
        this.yAxisValues = filtered_columns.map((value) => ({
            key: value,
            label: value.replaceAll("_", " ")
        }));
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

        this.records.forEach(record => {
            const peId = record.PE_ID;
            if (!groupedData[peId]) {
                groupedData[peId] = {
                    x: [],
                    y: [],
                    peId: peId
                };
            }
            groupedData[peId].x.push(record[this.selectedXAxis]);
            groupedData[peId].y.push(record[this.selectedYAxis]);
        });

        const traces = Object.values(groupedData).map(peData => ({
            x: peData.x,
            y: peData.y,
            showlegend: true
        }));

        Plotly.react(this.timePlotEl, traces, {
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
                pad: 4
            }
        });
    }
    }));
});
