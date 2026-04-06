import Alpine from 'alpinejs';
import { dataStore } from './dataStore.mjs';
import { dataFileSelector } from './partials/dataFileSelector.mjs';
import { heatmapPlot } from './plots/heatmap.mjs';
import { networkTimePlot } from './plots/networkTimePlot.mjs';
import { parallelCoords } from './plots/parallelCoords.mjs';
import { scatterPlot } from './plots/scatterPlot.mjs';
import { timePlot } from './plots/timePlot.mjs';

Alpine.store('dataStore', dataStore);
Alpine.data('dataFileSelector', dataFileSelector);
Alpine.data('heatmapPlot', heatmapPlot);
Alpine.data('networkTimePlot', networkTimePlot);
Alpine.data('parallelCoords', parallelCoords);
Alpine.data('scatterPlot', scatterPlot);
Alpine.data('timePlot', timePlot);
Alpine.start();
