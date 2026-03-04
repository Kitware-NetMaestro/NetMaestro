import Alpine from 'alpinejs';

import { dataStore } from './dataStore.js';
import { dataFileSelector } from './partials/dataFileSelector.js';
import { heatmapPlot } from './plots/heatmap.js';
import { networkTimePlot } from './plots/networkTimePlot.js';
import { parallelCoords } from './plots/parallelCoords.js';
import { scatterPlot } from './plots/scatterPlot.js';
import { timePlot } from './plots/timePlot.js';

Alpine.store('dataStore', dataStore);
Alpine.data('dataFileSelector', dataFileSelector);
Alpine.data('heatmapPlot', heatmapPlot);
Alpine.data('networkTimePlot', networkTimePlot);
Alpine.data('parallelCoords', parallelCoords);
Alpine.data('scatterPlot', scatterPlot);
Alpine.data('timePlot', timePlot);

Alpine.start();
