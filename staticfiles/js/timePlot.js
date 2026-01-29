function timePlotSetup(){
    const store = Alpine.store('dataStore')
    let records = []
    let columns = []
    let xAxisValues = [
        {
            key: "virtual_time",
            label: "Virtual Time"
        },
        {
            key: "real_time",
            label: "Real Time"
        },

    ]
    let yAxisValues = []

    let selectedXAxis = 'virtual_time'
    let selectedYAxis = 'events_processed'

    let minTime = null
    let maxTime = null


    function initPlot() {
        const timePlot = document.getElementById('timePlot');
        const data = [{
                x: [],
                y: [],
                showlegend: true,

            }]
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

            }
        const config = { responsive: true }
        Plotly.newPlot( timePlot, data, layout, config)
        store.loadRossData()
    }

    function processData(){
        const excluded_columns = ["PE_ID", "real_time", "virtual_time"]
        const filtered_columns = columns.filter(column => column && !excluded_columns.includes(column))
        yAxisValues = filtered_columns.map((value) => ({
            key: value,
            label: value.replaceAll("_", " ")
        }))
    }


    function updatePlotData() {
        const groupedData = {}

        records.forEach(record => {
            const peId = record.PE_ID
            if (!groupedData[peId]) {
                groupedData[peId] = {
                    x: [],
                    y: [],
                    peId: peId
                }
            }
            groupedData[peId].x.push(record[selectedXAxis])
            groupedData[peId].y.push(record[selectedYAxis])
        })

        const traces = Object.values(groupedData).map(peData => ({
            x: peData.x,
            y: peData.y,
            showlegend: true
        }))

        Plotly.react(timePlot, traces, {
            xaxis: {
                title: {
                    text: xAxisValues.find((item) => item.key === selectedXAxis).label,
                },
                color: 'white',
            },
            yaxis: {
                title: {
                    text: yAxisValues.find((item) => item.key === selectedYAxis).label,
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
        xAxisValues,
        yAxisValues
    }
}
