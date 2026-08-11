"""Render processed trace tables as a multi-tab interactive HTML report."""

from __future__ import annotations

import json
from collections.abc import Sequence
from html import escape
from pathlib import Path

from plotly import __version__ as plotly_version
from plotly.offline import get_plotlyjs

from rawtrace_qc.processing.models import ProcessedTable
from rawtrace_qc.report.models import ReportDocument, ReportOptions
from rawtrace_qc.report.prepare import build_report


def write_html(
    processed_tables: Sequence[ProcessedTable],
    output_path: Path,
    *,
    options: ReportOptions | None = None,
) -> Path:
    """Create a multi-tab HTML report from processed tables.

    Args:
        processed_tables: Report-ready tables to include in the report.
        output_path: Destination HTML path. Parent directories are created when
            necessary.
        options: Report configuration. If None (default), uses all available
            channels and the default metadata fields.

    Returns:
        The resolved output path.

    Raises:
        ConfigurationError: If report options or requested channels are invalid.
        ReportError: If a processed table cannot be serialized for reporting.
    """
    report = build_report(processed_tables, options=options)
    resolved_path = output_path.expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(_render_document(report), encoding="utf-8")
    return resolved_path


def render_html(
    processed_tables: Sequence[ProcessedTable],
    *,
    options: ReportOptions | None = None,
) -> str:
    """Render processed tables to an HTML string without writing a file.

    Args:
        processed_tables: Report-ready tables to include in the report.
        options: Report configuration. If None (default), uses all available
            channels and the default metadata fields.

    Returns:
        A complete HTML document.
    """
    return _render_document(build_report(processed_tables, options=options))


def _render_document(report: ReportDocument) -> str:
    tabs = _render_tabs(report)
    plot_panel = _render_plot_panel(report)
    metadata_panel = _render_metadata_panel(report)
    plotly_asset = _plotly_asset(report)
    payload = _safe_json(_report_payload(report))
    active_panel = "plot-panel" if report.channels else "metadata-panel"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(report.title)}</title>
  {_css()}
</head>
<body>
  <div class="report-shell">
    <header class="report-header">
      <h1>{escape(report.title)}</h1>
      <p>{len(report.traces)} processed table(s), {len(report.channels)} channel(s)</p>
    </header>
    <nav class="report-tabs" role="tablist" aria-label="Report views">
      {tabs}
    </nav>
    <main>
      {plot_panel}
      {metadata_panel}
    </main>
  </div>
  <script id="rawtrace-report-data" type="application/json">{payload}</script>
  {plotly_asset}
  <script>
    {_javascript(active_panel)}
  </script>
</body>
</html>
"""


def _render_tabs(report: ReportDocument) -> str:
    buttons: list[str] = []
    for index, channel in enumerate(report.channels):
        active = index == 0
        buttons.append(
            _tab_button(
                label=channel.label,
                panel="plot-panel",
                channel=channel.key,
                active=active,
            )
        )
    buttons.append(
        _tab_button(
            label="Metadata",
            panel="metadata-panel",
            channel=None,
            active=not report.channels,
        )
    )
    return "\n      ".join(buttons)


def _tab_button(
    *,
    label: str,
    panel: str,
    channel: str | None,
    active: bool,
) -> str:
    channel_attribute = (
        "" if channel is None else f' data-channel="{escape(channel, quote=True)}"'
    )
    selected = "true" if active else "false"
    classes = "report-tab is-active" if active else "report-tab"
    return (
        f'<button class="{classes}" type="button" role="tab" '
        f'aria-selected="{selected}" data-panel="{panel}"{channel_attribute}>'
        f"{escape(label)}</button>"
    )


def _render_plot_panel(report: ReportDocument) -> str:
    if not report.channels:
        return ""
    ms_options = '<option value="all">All MS levels</option>' + "".join(
        f'<option value="{level}">MS{level}</option>'
        for level in report.available_ms_levels
    )
    controls = f"""
      <div class="report-toolbar">
        <label>MS level <select id="report-ms-level">{ms_options}</select></label>
        {_render_faims_control(report)}
        <label>View <select id="report-view">
          <option value="overlay">Overlay</option>
          <option value="stacked">Stacked</option>
        </select></label>
      </div>
      <div id="report-plot" role="img" aria-label="Chromatogram plot"></div>
"""
    return (
        '<section id="plot-panel" class="report-panel" role="tabpanel">'
        f"{controls}</section>"
    )


def _render_faims_control(report: ReportDocument) -> str:
    if not report.available_faims_values:
        return ""
    options = '<option value="all">All CVs</option>' + "".join(
        f'<option value="{escape(str(value), quote=True)}">'
        f"CV {escape(_display_faims_value(value))}</option>"
        for value in report.available_faims_values
    )
    return f'<label>FAIMS CV <select id="report-faims">{options}</select></label>'


def _render_metadata_panel(report: ReportDocument) -> str:
    if not report.metadata_rows:
        content = '<p class="empty-state">No processed tables were supplied.</p>'
    else:
        headers = "".join(
            f'<th scope="col">{escape(_field_label(field))}</th>'
            for field in report.metadata_fields
        )
        rows = []
        for row in report.metadata_rows:
            cells = "".join(
                f"<td>{escape(_display_metadata_value(value))}</td>"
                for _, value in row.values
            )
            rows.append(f"<tr>{cells}</tr>")
        content = (
            '<div class="metadata-table-wrap"><table class="metadata-table">'
            f"<thead><tr>{headers}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )
    return (
        '<section id="metadata-panel" class="report-panel" role="tabpanel">'
        f"{content}</section>"
    )


def _plotly_asset(report: ReportDocument) -> str:
    if not report.channels:
        return ""
    if report.asset_mode.value == "cdn":
        return (
            f'<script src="https://cdn.plot.ly/plotly-{plotly_version}.min.js">'
            "</script>"
        )
    return f"<script>{get_plotlyjs()}</script>"


def _report_payload(report: ReportDocument) -> dict[str, object]:
    return {
        "title": report.title,
        "initial_channel": report.initial_channel,
        "initial_view": report.initial_view.value,
        "channels": {
            channel.key: {
                "label": channel.label,
                "y_axis_title": channel.y_axis_title,
            }
            for channel in report.channels
        },
        "available_faims_values": list(report.available_faims_values),
        "traces": [
            {
                "name": trace.name,
                "source_key": trace.source_key,
                "ms_level": trace.ms_level,
                "faims_cv": trace.faims_cv,
                "color_index": trace.color_index,
                "retention_time_min": list(trace.retention_time_min),
                "channels": {
                    channel: list(values) for channel, values in trace.channels
                },
            }
            for trace in report.traces
        ],
    }


def _safe_json(value: object) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return (
        serialized.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _display_metadata_value(value: object) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, tuple):
        return ", ".join(value) or "None"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _display_faims_value(value: float | str) -> str:
    if isinstance(value, float):
        return f"{value:+g} V"
    return value


def _field_label(field_name: str) -> str:
    labels = {
        "ms_level": "MS level",
        "ms_level_file": "MS file",
        "faims_cv": "FAIMS CV",
        "rawfile_name": "Raw file",
        "row_granularity": "Row granularity",
        "time_unit": "Time unit",
        "source_id": "Source ID",
    }
    return labels.get(field_name, field_name.replace("_", " ").title())


def _css() -> str:
    return """<style>
    :root {
      color-scheme: light;
      --ink: #17212b;
      --muted: #617080;
      --line: #d5dde5;
      --surface: #ffffff;
      --canvas: #f3f6f8;
      --accent: #0b7285;
      --accent-soft: #d8f0f2;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      background: var(--canvas);
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
    }
    .report-shell { min-height: 100vh; }
    .report-header {
      padding: 28px clamp(18px, 4vw, 56px) 20px;
      background: linear-gradient(120deg, #e6f4f1, #f7f8f5 58%, #eaf0f5);
      border-bottom: 1px solid var(--line);
    }
    .report-header h1 {
      margin: 0;
      font-size: clamp(24px, 4vw, 38px);
      font-weight: 600;
    }
    .report-header p {
      margin: 8px 0 0;
      color: var(--muted);
      font-family: system-ui, sans-serif;
      font-size: 13px;
    }
    .report-tabs {
      display: flex;
      gap: 4px;
      padding: 12px clamp(18px, 4vw, 56px) 0;
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      overflow-x: auto;
    }
    .report-tab {
      border: 0;
      border-bottom: 3px solid transparent;
      padding: 11px 16px 10px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      font: 600 13px system-ui, sans-serif;
      white-space: nowrap;
    }
    .report-tab:hover, .report-tab.is-active { color: var(--accent); }
    .report-tab.is-active { border-bottom-color: var(--accent); }
    .report-panel { padding: 22px clamp(18px, 4vw, 56px) 42px; }
    .report-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 18px;
      align-items: center;
      margin-bottom: 14px;
      font: 12px system-ui, sans-serif;
      color: var(--muted);
    }
    .report-toolbar label { display: inline-flex; align-items: center; gap: 7px; }
    .report-toolbar select {
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 6px 8px;
      background: var(--surface);
      color: var(--ink);
      font: inherit;
    }
    #report-plot {
      width: 100%;
      min-height: 560px;
      background: var(--surface);
      border: 1px solid var(--line);
    }
    .metadata-table-wrap {
      overflow-x: auto;
      background: var(--surface);
      border: 1px solid var(--line);
    }
    .metadata-table {
      width: 100%;
      min-width: 720px;
      border-collapse: collapse;
      font: 13px system-ui, sans-serif;
    }
    .metadata-table th, .metadata-table td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    .metadata-table th {
      background: #edf3f5;
      color: #40515f;
      font-size: 11px;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .metadata-table tr:last-child td { border-bottom: 0; }
    .empty-state {
      padding: 42px 18px;
      color: var(--muted);
      font: 14px system-ui, sans-serif;
      text-align: center;
    }
    @media (max-width: 640px) {
      .report-panel { padding-top: 16px; }
      #report-plot { min-height: 420px; }
    }
    </style>"""


def _javascript(active_panel: str) -> str:
    return f"""
    (function () {{
      var data = JSON.parse(
        document.getElementById('rawtrace-report-data').textContent
      );
      var plot = document.getElementById('report-plot');
      var palette = [
        '#0b7285', '#d94841', '#5f3dc4', '#2b8a3e',
        '#e67700', '#1864ab', '#862e9c', '#495057'
      ];
      var state = {{
        channel: data.initial_channel,
        msLevel: 'all',
        cv: 'all',
        view: data.initial_view
      }};

      function dashForLevel(level) {{
        return {{1: 'solid', 2: 'dash', 3: 'dot', 4: 'dashdot'}}[level]
          || 'longdashdot';
      }}
      function sameCv(left, right) {{
        if (typeof left === 'number') return Number(right) === left;
        return String(left) === String(right);
      }}
      function isVisible(trace) {{
        if (
          state.msLevel !== 'all'
          && trace.ms_level !== Number(state.msLevel)
        ) return false;
        if (trace.faims_cv === null || trace.faims_cv === undefined) return true;
        return state.cv === 'all' || sameCv(trace.faims_cv, state.cv);
      }}
      function activeTraces() {{
        return data.traces.filter(isVisible).filter(function (trace) {{
          return trace.channels[state.channel] !== undefined;
        }});
      }}
      function baseLayout() {{
        var channelSpec = data.channels[state.channel] || {{}};
        return {{
          template: 'plotly_white',
          autosize: true,
          title: {{text: data.title, x: 0.02, xanchor: 'left', font: {{size: 16}}}},
          margin: {{l: 70, r: 24, t: 56, b: 64}},
          hovermode: 'x unified',
          xaxis: {{
            title: 'Retention time (min)',
            showgrid: true,
            gridcolor: '#e1e7eb'
          }},
          yaxis: {{
            title: channelSpec.y_axis_title || 'Intensity',
            showgrid: true,
            gridcolor: '#e1e7eb',
            exponentformat: 'E'
          }},
          legend: {{orientation: 'h', y: -0.2, yanchor: 'top'}},
        }};
      }}
      function makeTrace(trace, index, xAxis, yAxis) {{
        var item = {{
          x: trace.retention_time_min,
          y: trace.channels[state.channel],
          type: 'scattergl',
          mode: 'lines',
          name: trace.name,
          legendgroup: trace.source_key,
          line: {{
            color: palette[trace.color_index % palette.length],
            width: 1.5,
            dash: dashForLevel(trace.ms_level)
          }},
          hovertemplate: 'RT: %{{x:.2f}} min<br>Intensity: %{{y:.3e}}<extra>'
            + trace.name + '</extra>'
        }};
        if (xAxis) item.xaxis = xAxis;
        if (yAxis) item.yaxis = yAxis;
        return item;
      }}
      function render() {{
        if (!plot || !window.Plotly || !state.channel) return;
        var active = activeTraces();
        var layout = baseLayout();
        var traces;
        if (state.view === 'stacked' && active.length) {{
          layout.grid = {{
            rows: active.length,
            columns: 1,
            pattern: 'independent',
            roworder: 'top to bottom'
          }};
          delete layout.xaxis;
          delete layout.yaxis;
          traces = active.map(function (trace, index) {{
            var suffix = index === 0 ? '' : String(index + 1);
            layout['xaxis' + suffix] = {{
              title: index === active.length - 1 ? 'Retention time (min)' : '',
              matches: index ? 'x' : undefined,
              showgrid: true,
              gridcolor: '#e1e7eb'
            }};
            layout['yaxis' + suffix] = {{
              title: trace.name,
              showgrid: true,
              gridcolor: '#e1e7eb',
              exponentformat: 'E'
            }};
            return makeTrace(trace, index, 'x' + suffix, 'y' + suffix);
          }});
        }} else {{
          traces = active.map(function (trace, index) {{
            return makeTrace(trace, index, null, null);
          }});
        }}
        Plotly.react(
          plot,
          traces,
          layout,
          {{responsive: true, displaylogo: false, scrollZoom: true}}
        );
      }}
      function activateTab(button) {{
        document.querySelectorAll('.report-tab').forEach(function (item) {{
          var active = item === button;
          item.classList.toggle('is-active', active);
          item.setAttribute('aria-selected', active ? 'true' : 'false');
        }});
        document.querySelectorAll('.report-panel').forEach(function (panel) {{
          panel.hidden = panel.id !== button.dataset.panel;
        }});
        if (button.dataset.channel) {{
          state.channel = button.dataset.channel;
          render();
        }}
      }}
      document.querySelectorAll('.report-tab').forEach(function (button) {{
        button.addEventListener('click', function () {{ activateTab(button); }});
      }});
      var ms = document.getElementById('report-ms-level');
      if (ms) ms.addEventListener('change', function () {{
        state.msLevel = ms.value;
        render();
      }});
      var cv = document.getElementById('report-faims');
      if (cv) cv.addEventListener('change', function () {{
        state.cv = cv.value;
        render();
      }});
      var view = document.getElementById('report-view');
      if (view) {{
        view.value = state.view;
        view.addEventListener('change', function () {{
          state.view = view.value;
          render();
        }});
      }}
      document.getElementById('{active_panel}').hidden = false;
      document.querySelectorAll('.report-panel').forEach(function (panel) {{
        if (panel.id !== '{active_panel}') panel.hidden = true;
      }});
      render();
    }})();
    """
