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

    /**
     * Initialize the component and set up watchers.
     * Called automatically by Alpine.js when component mounts.
     */
    init() {
        const store = Alpine.store('dataStore');
        this.initPlot();

        // Watch for data changes - automatically cleaned up on component destroy
        this.$watch(() => store.rossData, (data) => {
            if (!data) return;
            this.columns = data.columns;
            this.records = data.data;
            this.processData();
            this.updatePlotData();
        });
    },

    /**
     * Initialize the Plotly time plot.
     */
    initPlot() {
        const timePlot = document.getElementById('timePlot');
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
        Plotly.newPlot(timePlot, data, layout, config);

        // Load initial data
        const store = Alpine.store('dataStore');
        store.loadRossData();
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

        const timePlot = document.getElementById('timePlot');
        Plotly.react(timePlot, traces, {
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
