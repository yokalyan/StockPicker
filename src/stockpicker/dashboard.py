from __future__ import annotations

from html import escape

from stockpicker.models import Opportunity


def render_dashboard(opportunities: list[Opportunity]) -> str:
    rows = "\n".join(_render_row(index, item) for index, item in enumerate(opportunities, start=1))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>StockPicker Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --ink: #18202a;
      --muted: #667085;
      --line: #d9dee7;
      --good: #0f7b5f;
      --watch: #9a5b00;
      --bad: #a43d3d;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      margin-bottom: 20px;
    }}
    h1 {{
      font-size: 28px;
      margin: 0 0 4px;
      letter-spacing: 0;
    }}
    .subtle {{
      color: var(--muted);
      font-size: 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      background: #eef1f5;
      color: #344054;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    .score {{
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }}
    .status {{
      display: inline-block;
      white-space: nowrap;
      font-size: 12px;
      padding: 3px 7px;
      border-radius: 999px;
      background: #eef1f5;
      color: #344054;
    }}
    .status.below_sponsor_cost, .status.inside_buy_zone {{
      background: #e7f5ef;
      color: var(--good);
    }}
    .status.interesting_too_expensive {{
      background: #fff2d8;
      color: var(--watch);
    }}
    .status.rejected {{
      background: #fce8e8;
      color: var(--bad);
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>StockPicker Dashboard</h1>
        <div class="subtle">Ranked filing-derived research queue</div>
      </div>
      <div class="subtle">{len(opportunities)} opportunities</div>
    </header>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Ticker</th>
          <th>Score</th>
          <th>Signal</th>
          <th>Price Status</th>
          <th>Managers</th>
          <th>Why It Matters</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def _render_row(index: int, item: Opportunity) -> str:
    rationale = "".join(f"<li>{escape(reason)}</li>" for reason in item.rationale[:4])
    status = escape(item.price_status.value)
    managers = escape(", ".join(item.managers))
    ticker_cell = (
        f"<strong>{escape(item.ticker)}</strong><br>"
        f'<span class="subtle">{escape(item.issuer_name)}</span>'
    )
    return f"""<tr>
  <td>{index}</td>
  <td>{ticker_cell}</td>
  <td class="score">{item.score:.1f}</td>
  <td>{escape(item.best_signal.value)}</td>
  <td><span class="status {status}">{status.replace("_", " ")}</span></td>
  <td>{managers}</td>
  <td><ul>{rationale}</ul></td>
</tr>"""
