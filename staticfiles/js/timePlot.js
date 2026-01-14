function timePlotSetup(){
    function initPlot() {
        const scatterPlot = document.getElementById('timePlot');
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
                        text: 'Virtual Time'
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

    }
    return {
        initPlot
    }
}
