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
    ms_options = "".join(
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
        <label>Reference trace <select id="report-reference">
          <option value="">None</option>
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
        "available_ms_levels": list(report.available_ms_levels),
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
                "table_index": trace.table_index,
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
      --facility-blue: #063853;
      --facility-teal: #40B7B5;
      --facility-red: #E73C40;
      --ink: #163342;
      --muted: #5f747e;
      --line: #d3e1e5;
      --surface: #ffffff;
      --surface-raised: #f8fbfb;
      --canvas: #edf4f5;
      --accent: #0e6f76;
      --accent-soft: #e4f5f4;
      --focus: rgba(64, 183, 181, .42);
    }
    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    body {
      margin: 0;
      min-width: 320px;
      background: var(--canvas);
      color: var(--ink);
      font-family: "Aptos", "Segoe UI", "Helvetica Neue", sans-serif;
      line-height: 1.45;
    }
    .report-shell { min-height: 100vh; }
    .report-header {
      padding: 32px clamp(18px, 4vw, 56px) 25px;
      background: linear-gradient(120deg, var(--facility-blue), #0a506b 68%, #146d79);
      color: var(--surface);
      border-top: 4px solid var(--facility-teal);
      border-bottom: 2px solid var(--facility-red);
      box-shadow: 0 3px 10px rgba(6, 56, 83, .12);
    }
    .report-header h1 {
      margin: 0;
      font-family: "Aptos Display", "Aptos", "Segoe UI", sans-serif;
      font-size: 32px;
      line-height: 1.1;
      font-weight: 700;
      letter-spacing: 0;
    }
    .report-header p {
      margin: 10px 0 0;
      color: #d8ebee;
      font-size: 13px;
      font-weight: 500;
    }
    .report-tabs {
      display: flex;
      gap: 2px;
      padding: 0 clamp(18px, 4vw, 56px);
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      overflow-x: auto;
      position: sticky;
      top: 0;
      z-index: 10;
      box-shadow: 0 2px 8px rgba(6, 56, 83, .08);
    }
    .report-tab {
      min-height: 48px;
      border: 0;
      border-bottom: 3px solid transparent;
      padding: 13px 16px 11px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      font: 600 13px "Aptos", "Segoe UI", "Helvetica Neue", sans-serif;
      white-space: nowrap;
      transition: color .15s ease, background-color .15s ease, border-color .15s ease;
    }
    .report-tab:hover {
      background: var(--accent-soft);
      color: var(--facility-blue);
    }
    .report-tab.is-active {
      border-bottom-color: var(--facility-teal);
      color: var(--facility-blue);
      background: linear-gradient(to bottom, var(--surface), #f4fbfb);
    }
    .report-tab:focus-visible,
    .report-toolbar select:focus-visible {
      outline: 3px solid var(--focus);
      outline-offset: 2px;
    }
    .report-panel {
      max-width: 1680px;
      margin: 0 auto;
      padding: 24px clamp(18px, 4vw, 56px) 48px;
    }
    .report-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 20px;
      align-items: center;
      margin-bottom: 16px;
      padding: 11px 13px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 4px solid var(--facility-teal);
      border-radius: 6px;
      box-shadow: 0 2px 8px rgba(6, 56, 83, .06);
      color: var(--facility-blue);
      font-size: 12px;
      font-weight: 600;
    }
    .report-toolbar label {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .report-toolbar select {
      min-height: 34px;
      border: 1px solid #b9ccd2;
      border-radius: 4px;
      padding: 6px 30px 6px 10px;
      background: var(--surface);
      color: var(--facility-blue);
      cursor: pointer;
      font: 600 13px "Aptos", "Segoe UI", "Helvetica Neue", sans-serif;
    }
    .report-toolbar select:hover {
      border-color: var(--accent);
      background: var(--surface-raised);
    }
    #report-plot {
      width: 100%;
      min-height: 560px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 6px;
      box-shadow: 0 3px 12px rgba(6, 56, 83, .08);
      overflow: hidden;
    }
    #report-plot .modebar { top: 8px !important; right: 8px !important; }
    .metadata-table-wrap {
      overflow-x: auto;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 6px;
      box-shadow: 0 3px 12px rgba(6, 56, 83, .07);
    }
    .metadata-table {
      width: 100%;
      min-width: 720px;
      border-collapse: collapse;
      font: 13px "Aptos", "Segoe UI", "Helvetica Neue", sans-serif;
      font-variant-numeric: tabular-nums;
    }
    .metadata-table th, .metadata-table td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    .metadata-table th {
      background: var(--facility-blue);
      border-bottom: 3px solid var(--facility-teal);
      color: #ffffff;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .metadata-table tbody tr:nth-child(even) td { background: var(--surface-raised); }
    .metadata-table tbody tr:hover td { background: #eef9f8; }
    .metadata-table tr:last-child td { border-bottom: 0; }
    .empty-state {
      margin: 0;
      padding: 42px 18px;
      background: var(--surface);
      border: 1px dashed #b9ccd2;
      border-radius: 6px;
      color: var(--muted);
      font-size: 14px;
      text-align: center;
    }
    @media (max-width: 640px) {
      .report-header { padding: 24px 16px 20px; }
      .report-header h1 { font-size: 26px; }
      .report-tabs { padding: 0 12px; }
      .report-tab { padding-inline: 13px; }
      .report-panel { padding: 16px 12px 30px; }
      .report-toolbar { align-items: stretch; padding: 12px; }
      .report-toolbar label { flex: 1 1 160px; justify-content: space-between; }
      .report-toolbar select { flex: 1; }
      #report-plot { min-height: 420px; }
      .metadata-table { min-width: 640px; }
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
        '#063853', '#40B7B5', '#2F6F9F', '#26734D',
        '#856F00', '#624A91', '#765B45', '#596B78',
        '#5F7F2F', '#936A2F'
      ];
      var REFERENCE_COLOR = '#E73C40';
      var NORMAL_PLOT_HEIGHT = 560;
      var STACKED_TRACE_HEIGHT = 280;
      var state = {{
        channel: data.initial_channel,
        msLevel: data.available_ms_levels.length
          ? data.available_ms_levels[0]
          : null,
        cv: 'all',
        view: data.initial_view,
        referenceTrace: null
      }};
      var reference = document.getElementById('report-reference');

      function sameCv(left, right) {{
        if (typeof left === 'number') return Number(right) === left;
        return String(left) === String(right);
      }}
      function isVisible(trace) {{
        if (state.msLevel !== null && trace.ms_level !== state.msLevel) return false;
        if (trace.faims_cv === null || trace.faims_cv === undefined) return true;
        return state.cv === 'all' || sameCv(trace.faims_cv, state.cv);
      }}
      function activeTraces() {{
        return data.traces.filter(isVisible).filter(function (trace) {{
          return trace.channels[state.channel] !== undefined;
        }});
      }}
      function orderedTraces(active) {{
        if (state.view !== 'overlay' || state.referenceTrace === null) return active;
        var referenceTrace = active.find(function (trace) {{
          return trace.table_index === state.referenceTrace;
        }});
        if (!referenceTrace) return active;
        return active.filter(function (trace) {{
          return trace.table_index !== state.referenceTrace;
        }}).concat([referenceTrace]);
      }}
      function updateReferenceOptions(active) {{
        if (!reference) return;
        var selected = state.referenceTrace;
        var selectedIsVisible = active.some(function (trace) {{
          return trace.table_index === selected;
        }});
        if (!selectedIsVisible) {{
          state.referenceTrace = null;
          selected = null;
        }}
        while (reference.firstChild) reference.removeChild(reference.firstChild);
        var none = document.createElement('option');
        none.value = '';
        none.textContent = 'None';
        reference.appendChild(none);
        active.forEach(function (trace) {{
          var option = document.createElement('option');
          option.value = String(trace.table_index);
          option.textContent = trace.name;
          reference.appendChild(option);
        }});
        reference.value = selected === null ? '' : String(selected);
      }}
      function baseLayout() {{
        var channelSpec = data.channels[state.channel] || {{}};
        return {{
          template: 'plotly_white',
          paper_bgcolor: '#ffffff',
          plot_bgcolor: '#fbfdfd',
          autosize: true,
          font: {{
            family: '"Aptos", "Segoe UI", "Helvetica Neue", sans-serif',
            color: '#163342',
            size: 12
          }},
          title: {{
            text: data.title,
            x: 0.02,
            xanchor: 'left',
            font: {{
              family: '"Aptos Display", "Aptos", "Segoe UI", sans-serif',
              color: '#063853',
              size: 16
            }}
          }},
          margin: {{l: 78, r: 24, t: 58, b: 82}},
          hovermode: 'x unified',
          hoverlabel: {{
            bgcolor: '#063853',
            bordercolor: '#40B7B5',
            font: {{color: '#ffffff'}}
          }},
          xaxis: {{
            title: 'Retention time (min)',
            showgrid: true,
            gridcolor: '#dce8eb',
            zerolinecolor: '#b9ccd2',
            linecolor: '#b9ccd2',
            ticks: 'outside'
          }},
          yaxis: {{
            title: channelSpec.y_axis_title || 'Intensity',
            showgrid: true,
            gridcolor: '#dce8eb',
            zerolinecolor: '#b9ccd2',
            linecolor: '#b9ccd2',
            exponentformat: 'E',
            ticks: 'outside'
          }},
          legend: {{
            orientation: 'h',
            x: 0,
            y: -0.22,
            xanchor: 'left',
            yanchor: 'top',
            bgcolor: 'rgba(255, 255, 255, .9)',
            bordercolor: '#d3e1e5',
            borderwidth: 1,
            font: {{size: 11, color: '#163342'}}
          }},
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
            color: trace.table_index === state.referenceTrace
              ? REFERENCE_COLOR
              : palette[trace.color_index % palette.length],
            width: 1.25
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
        updateReferenceOptions(active);
        active = orderedTraces(active);
        var layout = baseLayout();
        var traces;
        if (state.view === 'stacked' && active.length) {{
          var stackedHeight = active.length * STACKED_TRACE_HEIGHT;
          plot.style.height = stackedHeight + 'px';
          plot.style.minHeight = stackedHeight + 'px';
          layout.height = stackedHeight;
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
              gridcolor: '#dce8eb',
              zerolinecolor: '#b9ccd2',
              linecolor: '#b9ccd2',
              ticks: 'outside'
            }};
            layout['yaxis' + suffix] = {{
              title: trace.name,
              showgrid: true,
              gridcolor: '#dce8eb',
              zerolinecolor: '#b9ccd2',
              linecolor: '#b9ccd2',
              exponentformat: 'E',
              ticks: 'outside'
            }};
            return makeTrace(trace, index, 'x' + suffix, 'y' + suffix);
          }});
        }} else {{
          traces = active.map(function (trace, index) {{
            return makeTrace(trace, index, null, null);
          }});
          plot.style.height = NORMAL_PLOT_HEIGHT + 'px';
          plot.style.minHeight = NORMAL_PLOT_HEIGHT + 'px';
          layout.height = NORMAL_PLOT_HEIGHT;
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
      if (ms) {{
        ms.value = String(state.msLevel);
        ms.addEventListener('change', function () {{
          state.msLevel = Number(ms.value);
          render();
        }});
      }}
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
      if (reference) reference.addEventListener('change', function () {{
        state.referenceTrace = reference.value === ''
          ? null
          : Number(reference.value);
        render();
      }});
      document.getElementById('{active_panel}').hidden = false;
      document.querySelectorAll('.report-panel').forEach(function (panel) {{
        if (panel.id !== '{active_panel}') panel.hidden = true;
      }});
      render();
    }})();
    """
