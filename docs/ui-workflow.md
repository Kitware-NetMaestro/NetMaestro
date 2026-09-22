# UI Workflow

This guide walks through the NetMaestro UI from model selection through simulation results.

## 1. Choose a Simulation Model

The **Available Models** page is the starting point. Each simulation model is shown as an expandable card with its engine, category, and description. Expanding a card reveals the component models it uses.

```{image} images/available_models.png
:alt: Available Models page showing simulation model cards
```

Active models have a **Get Started** button that navigates to the next step. Models marked **Coming Soon** are not yet available.

| Model           | Engine | Status       | Entry Point          |
|----------------|--------|-------------|----------------------|
| Fluid Flow WAN | CODES  | Active      | Custom Components    |
| PHOLD          | ROSS   | Active      | Simulation Config    |
| Ping Pong      | CODES  | Coming Soon | -                    |
| ESnet          | CODES  | Coming Soon | -                    |

## 2. Create Custom Components

For models that use component-based topologies (like Fluid Flow WAN), the next step is creating **custom components** - presets with specific parameter values.

### Sidebar: Base Models

The left sidebar lists the available base component models. Clicking one opens the new component form with that base model pre-selected.

```{image} images/custom_components_sidebar.png
:alt: Custom components page with base model sidebar
```

### New Component Form

The form has three sections:

1. **Base Model** - select from the dropdown (or pre-populated from the sidebar). Selecting a base model shows its type, engine, and description.

2. **Component Details** - name and optional description for this preset.

3. **Parameters** - fields specific to the selected base model, with appropriate input types.

```{image} images/new_component_form.png
:alt: New component form with fluid-flow-wan-switch-lp selected
```

For a `fluid-flow-wan-switch-lp` component, the parameter fields are:

| Parameter              | Unit | Range    | Description                    |
|-----------------------|------|----------|--------------------------------|
| **Switch Buffer**     | Gb   | 1–256    | Shared buffer pool size        |
| **Terminal Bandwidth** | Gbps | 1–400    | Access link rate per terminal  |

After saving, the component appears in the custom components list and is available for use in the topology editor.

```{image} images/custom_components_page.png
:alt: Custom components page with base model sidebar
```

## 3. Build a Topology

```{image} images/topology.png
:alt: Topology preview with switches and connections
```

The **Topology** page lets you create or edit network topologies. Select an existing topology from the dropdown to preview it, or click **Create New** to open the editor.

```{image} images/edit_topology.png
:alt: Topology editor dialog with switches and connections
```

### Adding Switches

Click **Add New Switch** to choose from your custom switch components. The switch is added with defaults from the component (buffer size, terminal bandwidth), and you can adjust any field.

Each switch has:
- A **name** (auto-assigned A–Z, editable)
- **Terminals** count
- **Terminal bandwidth** (Gbps)
- **Switch buffer** (Gb)
- **Connections** to other switches with bandwidth

### Connections

Add connections between switches by clicking the **+** button in a switch's connections section. Select the target switch and specify the bandwidth. Connections are directional.

### Saving

The editor validates the topology before saving:
- At least 2 switches required
- Unique switch names
- At least 1 connection
- Positive bandwidth and buffer values

Saved topologies appear in the dropdown and are written as YAML files that the simulation model reads directly.

## 4. Configure and Run a Simulation

### PHOLD

The PHOLD simulation form lets you configure engine and model parameters directly - no topology step is needed.

```{image} images/new_simulation.png
:alt: PHOLD simulation configuration form
```

Key parameters include synchronization protocol, LPs per processor, remote event rate, and memory settings. Click **Save and Run** to start the simulation, or **Save** to store the configuration for later.

### Fluid Flow WAN

The workflow is: custom components &#8594; topology &#8594; traffic configuration &#8594; run.

## 5. View Results

The **Analysis** page shows completed simulation runs. Select a run to view its data across multiple visualizations.

```{image} images/results.png
:alt: Analysis page with simulation results
```

Available visualizations include time-series plots, heatmaps, scatter plots, and parallel coordinates.

---
