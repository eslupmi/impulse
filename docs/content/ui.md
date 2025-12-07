# UI [↰](config_file.md/#ui)

The interface provides multi-level sorting, filtering, and data coloring capabilities. It includes a theme toggle and the ability to expand incidents to view their details and contained alerts.

The interface uses WebSocket for communication on the `/ws` path. If you use a reverse proxy, don't forget to properly forward the traffic.

![None](https://github.com/eslupmi/site/blob/main/static/ui.png?raw=true)

## Elements

The UI contains several element blocks

In the **top right**, you can see a filter input field. The field supports Alertmanager-like expressions, including regex.

In the **bottom left**, there is an "online" / "offline" indicator to help you understand how current the information you're viewing is.

In the **bottom center**, there is a page switcher.

In the **bottom right**, there are buttons. Currently, there are 2:

- archive - for displaying historical data (incidents in "closed" status)
- light / dark theme - theme switcher

In the **center** is the main working element, the table.

## Table

### Columns

Each incident is represented as a row of selected fields. On the left there is an indicator of the current [status](concepts/incident.md#statuses-and-their-colors), on the right - a button to expand the incident and an indicator of the number of alerts in it.

Columns are selected through [configuration](config_file.md#uicolumns)

### Sorting

Default values are set in the [configuration file](config_file.md#uisorting).

To change the sort order, click the corresponding key in the column header. If you need to select sorting by multiple columns, select several by holding the **Ctrl** key.

### Filters

Default values are set in the [configuration file](config_file.md#uifilters).

Alert labels and column names can be used as filters. If a column name matches a label, the column name takes priority.

Examples: `job="node"`, `severity!="critical"`.

Regular expressions are also supported: `severity=~"warning|critical"`, `severity!~"info"`.
