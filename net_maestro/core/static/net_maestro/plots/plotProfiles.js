/**
 * Per-simulation-type plot settings, keyed by Run.simulation_type.
 * Add an entry when a new simulation type is added, affecting the generation of plots
 */

// Event trace, CODES model stats and ROSS engine stats: produced by PHOLD and ingested ESnet runs.
const ROSS_PROFILE = {
  heatmap: {
    dataset: 'event',
    sourceKey: 'source_lp',
    destKey: 'dest_lp',
    xTitle: 'Receiving LP ID',
    yTitle: 'Sending LP ID',
    metrics: [
      { key: 'num_messages', label: 'Num Messages', aggregate: 'count' },
      {
        key: 'bytes_sent',
        label: 'Bytes Sent (not available)',
        disabled: true,
        tooltip: 'Message size data not available in current event trace format',
      },
    ],
  },
  networkTime: {
    dataset: 'model',
    groupBy: 'lp_id',
    excludedColumns: ['lp_id', 'component_id', 'real_time', 'virtual_time'],
    timeAxes: [
      { key: 'virtual_time', label: 'Virtual Time' },
      { key: 'real_time', label: 'Real Time' },
    ],
    defaults: { x: 'virtual_time', y: 'send_count' },
  },
  simulation: {
    dataset: 'ross',
    groupBy: 'PE_ID',
    excludedColumns: ['PE_ID', 'real_time', 'virtual_time'],
    timeAxes: [
      { key: 'virtual_time', label: 'Virtual Time' },
      { key: 'real_time', label: 'Real Time' },
    ],
    scatterDefaults: { x: 'events_processed', y: 'events_rolled_back' },
    timeDefaults: { x: 'virtual_time', y: 'events_processed' },
    parallelDimensions: [
      { key: 'PE_ID', label: 'PE ID' },
      { key: 'events_processed', label: 'Events Processed' },
      { key: 'events_rolled_back', label: 'Events Rolled Back' },
      { key: 'total_rollbacks', label: 'Total Rollbacks' },
      { key: 'secondary_rollbacks', label: 'Secondary Rollbacks' },
    ],
  },
};

// Fluid-flow WAN model stats: switch, per-port and terminal samples from the analysis LPs.
const FFW_SAMPLE_COLUMNS = [
  'stats_type',
  'ts',
  'real_time',
  'gvt',
  'end_time',
  'peid',
  'kpid',
  'lpid',
];
const FFW_TIME_AXES = [
  { key: 'ts', label: 'Virtual Time' },
];
// biome-ignore lint/style/useNamingConvention: matches the API's ?stats_type= query param
const FFW_PARAMS = { stats_type: 'vt' };

const FFW_PROFILE = {
  heatmap: {
    dataset: 'ffw-ports',
    params: FFW_PARAMS,
    sourceKey: 'switch_id',
    destKey: 'target_index',
    // Switch-to-switch links only; terminal-facing ports would mix terminal and switch IDs.
    include: (record) => !record.is_terminal,
    xTitle: 'Destination Switch',
    yTitle: 'Source Switch',
    metrics: [
      { key: 'port_sent_mbit', label: 'Sent (Mbit)', aggregate: 'sum' },
      { key: 'port_queued_mbit', label: 'Queued (Mbit)', aggregate: 'sum' },
      { key: 'port_pause_time_ns', label: 'Pause Time (ns)', aggregate: 'sum' },
    ],
  },
  networkTime: {
    dataset: 'ffw-terminals',
    params: FFW_PARAMS,
    groupBy: 'terminal_id',
    excludedColumns: [...FFW_SAMPLE_COLUMNS, 'terminal_id', 'attached_switch'],
    timeAxes: FFW_TIME_AXES,
    defaults: { x: 'ts', y: 'send_rate_sum_mbps' },
  },
  simulation: {
    dataset: 'ffw-switches',
    params: FFW_PARAMS,
    groupBy: 'switch_id',
    excludedColumns: [...FFW_SAMPLE_COLUMNS, 'switch_id', 'num_ports'],
    timeAxes: FFW_TIME_AXES,
    scatterDefaults: { x: 'shared_buffer_occupancy_mbit', y: 'sent_mbit' },
    timeDefaults: { x: 'ts', y: 'sent_mbit' },
    parallelDimensions: [
      { key: 'switch_id', label: 'Switch ID' },
      { key: 'sent_mbit', label: 'Sent (Mbit)' },
      { key: 'delivered_local_mbit', label: 'Delivered Local (Mbit)' },
      { key: 'dropped_mbit', label: 'Dropped (Mbit)' },
      { key: 'shared_buffer_occupancy_mbit', label: 'Buffer Occupancy (Mbit)' },
      { key: 'pause_frames_sent', label: 'Pause Frames Sent' },
    ],
  },
};

const PLOT_PROFILES = {
  phold: ROSS_PROFILE,
  esnet: ROSS_PROFILE,
  ffw: FFW_PROFILE,
};

/** Return the plot profile for a simulation type, defaulting to the ROSS profile. */
export function plotProfileFor(simulationType) {
  return PLOT_PROFILES[simulationType] ?? ROSS_PROFILE;
}
