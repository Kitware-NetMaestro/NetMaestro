function scatterPlotSetup() {
    const store = Alpine.store('dataStore')
    let records = []
    let columns = []
    let valueList = []

    let selectedXAxis = 'events_processed'
    let selectedYAxis = 'events_rolled_back'

    function initPlot() {
        const scatterPlot = document.getElementById('scatterPlot');
        const data = [{
                x: [],
                y: [],
                mode: 'markers',
                type: 'scatter',
                showlegend: true,

            }]
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

            }
        const config = { responsive: true }
        Plotly.newPlot( scatterPlot, data, layout, config)
            // TODO: When File selection is available change this to be fired then
            store.loadRossData()
    }

    function processData(){
        const excluded_columns = ["PE_ID", "real_time", "virtual_time"]
        const filtered_columns = columns.filter(column => column && !excluded_columns.includes(column))
        valueList = filtered_columns.map((value) => ({
            key: value,
            label: value.replaceAll("_", " ")
        }))
    }

    function updatePlotData() {
        const xData = records.map(record => record[selectedXAxis])
        const yData = records.map(record => record[selectedYAxis])

        // TODO: This could be another choice we allow the user to make.
        const color_range = records.map(record => record.PE_ID)

        Plotly.update(scatterPlot, {
            x: [xData],
            y: [yData],
            marker:{
                color: color_range,
                colorscale: 'Blues'
            }
        },{
            xaxis: {
                title: {
                    text: valueList.find((item) => item.key === selectedXAxis).label,
                },
                color: 'white',
            },
            yaxis: {
                title: {
                    text: valueList.find((item) => item.key === selectedYAxis).label,
                },
                color: 'white',
            }
        })
    }

    Alpine.watch(
        () => store.rossData,
        (data) => {
            if(!data){
                return
            }
            columns = data.columns
            records = data.data
            processData()
            updatePlotData()
        }
    )

    return {
        initPlot,
        selectedXAxis,
        selectedYAxis,
        valueList
    }
}
