# UI [↰](../config_file.md/#ui)

The interface provides multi-level sorting, filtering, and data coloring capabilities. It includes a theme toggle and the ability to expand incidents to view their details and contained alerts.

The interface uses WebSocket for communication on the `/ws` path. If you use a reverse proxy, don't forget to properly forward the traffic.

![None](https://github.com/eslupmi/site/blob/main/static/ui.png?raw=true)

## Elements

The UI consists of 3 parts:

- header
- table
- footer

### Header

The header shows current filters and a field for manually adding filters. More details [here](#filters).

### Table

Table of current incidents

### Footer

The footer can be divided into 3 parts:
- on the left is an "online" / "offline" indicator to help you understand how current the information you're viewing is.
- in the center is a page switcher
- on the right are 2 buttons: 
    - archive - for displaying historical data (incidents in [`closed` status](incident.md#closed))
    - theme switcher

## Features

### Columns

Each incident is represented as a row of selected fields. On the left there is an indicator of the current [status](incident.md#statuses-and-their-colors), on the right - a button to expand the incident and an indicator of the number of alerts in it.

Columns are selected through [configuration](../config_file.md#uicolumns)

### Sorting

Default values are set in the [configuration file](../config_file.md#uisorting).

To change the sort order, click the corresponding key in the column header. If you need to select sorting by multiple columns, select several by holding the **Ctrl** key.

### Filters

Alert labels and [column names](../config_file.md#columnname) can be used as filters. If a column name matches a label, the column name takes priority.

Default filters are set in the [configuration file](../config_file.md#uifilters).

Filters can be added using the filter [input field](#input-field) in the header or through the **+/-** buttons next to the table fields.

#### Input Field

The filter input field supports Alertmanager-like expressions, including regex.

Examples:

- `job = "node"`
- `severity != "critical"`
- `severity =~ "warning|critical"`
- `host !~ "elastic.*"`.
