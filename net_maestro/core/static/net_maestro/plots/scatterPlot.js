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
     * Initialize the Plotly scatter plot.
     */
    initPlot() {
        const scatterPlot = document.getElementById('scatterPlot');
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
        Plotly.newPlot(scatterPlot, data, layout, config);

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
        this.valueList = filtered_columns.map((value) => ({
            key: value,
            label: value.replaceAll("_", " ")
        }));
    },

    /**
     * Update the plot with current axis selections.
     */
    updatePlotData() {
        const xData = this.records.map(record => record[this.selectedXAxis]);
        const yData = this.records.map(record => record[this.selectedYAxis]);

        // TODO: This could be another choice we allow the user to make.
        const color_range = this.records.map(record => record.PE_ID);

        const scatterPlot = document.getElementById('scatterPlot');
        Plotly.update(scatterPlot, {
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
