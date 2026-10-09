from __future__ import annotations

from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from stockpicker.alerts import alerts_from_opportunities
from stockpicker.db import Database
from stockpicker.opportunities import rank_opportunities
from stockpicker.pipeline import build_cost_estimates_for_signals


@dataclass(frozen=True)
class WebServer:
    host: str
    port: int
    db_path: str

    def serve_forever(self) -> None:
        db = Database(self.db_path)
        db.init()
        handler = _handler_factory(db)
        server = ThreadingHTTPServer((self.host, self.port), handler)
        server.serve_forever()


def render_app(db: Database, section: str = "opportunities") -> str:
    db.init()
    sections = {
        "opportunities": _render_opportunities,
        "alerts": _render_alerts,
        "watchlist": _render_watchlist,
        "portfolio": _render_portfolio,
        "decisions": _render_decisions,
        "beneficial": _render_beneficial,
    }
    section = section if section in sections else "opportunities"
    content = sections[section](db)
    nav = "".join(
        _nav_link(slug, label, active=(slug == section))
        for slug, label in [
            ("opportunities", "Opportunities"),
            ("alerts", "Alerts"),
            ("watchlist", "Watchlist"),
            ("portfolio", "Portfolio"),
            ("decisions", "Decisions"),
            ("beneficial", "13D/13G"),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>StockPicker</title>
  <style>{_css()}</style>
</head>
<body>
  <aside>
    <div class="brand">StockPicker</div>
    <nav>{nav}</nav>
  </aside>
  <main>
    {content}
  </main>
</body>
</html>
"""


def _handler_factory(db: Database):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in {"/", "/dashboard"}:
                self.send_error(404)
                return
            query = parse_qs(parsed.query)
            section = query.get("section", ["opportunities"])[0]
            body = render_app(db, section=section).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def _ranked(db: Database):
    signals = db.signals()
    estimates = build_cost_estimates_for_signals(db=db, signals=signals)
    return rank_opportunities(signals=signals, managers=db.managers(), cost_estimates=estimates)


def _render_opportunities(db: Database) -> str:
    rows = "".join(
        f"""<tr>
          <td><strong>{escape(item.ticker)}</strong><span>{escape(item.issuer_name)}</span></td>
          <td class="num">{item.score:.1f}</td>
          <td>{escape(item.best_signal.value)}</td>
          <td>{_status(item.price_status.value)}</td>
          <td>{escape(", ".join(item.managers))}</td>
        </tr>"""
        for item in _ranked(db)[:50]
    )
    return _section(
        "Opportunities",
        "Ranked filing-derived research queue.",
        _table(["Ticker", "Score", "Signal", "Price", "Managers"], rows),
    )


def _render_alerts(db: Database) -> str:
    alerts = alerts_from_opportunities(_ranked(db)[:50], db.watchlist_by_ticker())
    rows = "".join(
        f"""<tr>
          <td class="num">{item.severity}</td>
          <td>{escape(item.alert_type.value)}</td>
          <td><strong>{escape(item.ticker)}</strong></td>
          <td>{escape(item.message)}</td>
        </tr>"""
        for item in alerts
    )
    return _section("Alerts", "Actionable changes since the last saved watchlist.", _table(
        ["Severity", "Type", "Ticker", "Message"], rows
    ))


def _render_watchlist(db: Database) -> str:
    rows = "".join(
        f"""<tr>
          <td>{_ticker_cell(item.ticker, item.issuer_name)}</td>
          <td>{escape(item.state.value)}</td>
          <td>{escape(item.last_price_status.value if item.last_price_status else "")}</td>
          <td class="num">{_number(item.opportunity_score)}</td>
        </tr>"""
        for item in db.watchlist()
    )
    return _section("Watchlist", "Persisted operating queue.", _table(
        ["Ticker", "State", "Price Status", "Score"], rows
    ))


def _render_portfolio(db: Database) -> str:
    rows = "".join(
        f"""<tr>
          <td>{_ticker_cell(item.ticker, item.issuer_name)}</td>
          <td>{escape(item.thesis_status.value)}</td>
          <td class="num">{_pct(item.target_weight)}</td>
          <td class="num">{_money(item.entry_price)}</td>
          <td class="num">{_money(item.add_below)}</td>
          <td>{escape(item.exit_condition)}</td>
        </tr>"""
        for item in db.portfolio_positions()
    )
    return _section("Portfolio", "Position plans and thesis guardrails.", _table(
        ["Ticker", "Status", "Target", "Entry", "Add Below", "Exit"], rows
    ))


def _render_decisions(db: Database) -> str:
    rows = "".join(
        f"""<tr>
          <td>{item.decision_date.isoformat()}</td>
          <td><strong>{escape(item.ticker)}</strong></td>
          <td>{escape(item.decision_type.value)}</td>
          <td class="num">{_money(item.price)}</td>
          <td>{escape(item.rationale)}</td>
        </tr>"""
        for item in db.decisions()
    )
    return _section("Decisions", "Durable investment decision journal.", _table(
        ["Date", "Ticker", "Type", "Price", "Rationale"], rows
    ))


def _render_beneficial(db: Database) -> str:
    rows = "".join(
        f"""<tr>
          <td>{item.filing_date.isoformat()}</td>
          <td>{_ticker_cell(item.ticker or "", item.issuer_name)}</td>
          <td>{escape(str(item.filing_type))}</td>
          <td class="num">{item.ownership_pct:.1f}%</td>
          <td class="num">{_range(item.price_low, item.price_high)}</td>
        </tr>"""
        for item in db.beneficial_ownership_filings()
    )
    return _section("13D/13G", "Beneficial ownership and activist filings.", _table(
        ["Date", "Issuer", "Type", "Ownership", "Price Range"], rows
    ))


def _section(title: str, subtitle: str, body: str) -> str:
    return f"""<header>
      <div>
        <h1>{escape(title)}</h1>
        <p>{escape(subtitle)}</p>
      </div>
    </header>
    {body}"""


def _table(headers: list[str], rows: str) -> str:
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    empty = f"""<tr><td colspan="{len(headers)}" class="empty">No records yet.</td></tr>"""
    return f"""<table>
      <thead><tr>{head}</tr></thead>
      <tbody>{rows or empty}</tbody>
    </table>"""


def _nav_link(slug: str, label: str, active: bool) -> str:
    cls = "active" if active else ""
    return f'<a class="{cls}" href="/dashboard?section={slug}">{escape(label)}</a>'


def _status(value: str) -> str:
    return f'<span class="pill {escape(value)}">{escape(value.replace("_", " "))}</span>'


def _ticker_cell(ticker: str, issuer_name: str | None) -> str:
    return f"<strong>{escape(ticker)}</strong><span>{escape(issuer_name or '')}</span>"


def _money(value: float | None) -> str:
    return "" if value is None else f"${value:,.2f}"


def _pct(value: float | None) -> str:
    return "" if value is None else f"{value:.1%}"


def _number(value: float | None) -> str:
    return "" if value is None else f"{value:.1f}"


def _range(low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return ""
    return f"${low:,.2f}-${high:,.2f}"


def _css() -> str:
    return """
    :root {
      --bg: #f5f7fa;
      --panel: #ffffff;
      --ink: #18202a;
      --muted: #667085;
      --line: #d6dce5;
      --nav: #101820;
      --nav-muted: #aab4c0;
      --green: #0f7b5f;
      --amber: #9a5b00;
      --red: #a43d3d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      grid-template-columns: 220px 1fr;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    aside {
      background: var(--nav);
      color: white;
      padding: 24px 16px;
    }
    .brand {
      font-size: 20px;
      font-weight: 700;
      margin-bottom: 24px;
    }
    nav { display: grid; gap: 4px; }
    nav a {
      color: var(--nav-muted);
      text-decoration: none;
      padding: 10px 12px;
      border-radius: 6px;
      font-size: 14px;
    }
    nav a.active, nav a:hover {
      background: #263241;
      color: white;
    }
    main { padding: 28px; min-width: 0; }
    header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }
    h1 { margin: 0; font-size: 26px; letter-spacing: 0; }
    p { margin: 4px 0 0; color: var(--muted); }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    th, td {
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }
    th {
      background: #edf1f5;
      color: #344054;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }
    tr:last-child td { border-bottom: 0; }
    td span {
      display: block;
      color: var(--muted);
      margin-top: 2px;
      font-size: 12px;
    }
    .num { font-variant-numeric: tabular-nums; white-space: nowrap; }
    .empty { text-align: center; color: var(--muted); padding: 28px; }
    .pill {
      display: inline-block;
      white-space: nowrap;
      padding: 3px 7px;
      border-radius: 999px;
      background: #eef1f5;
      color: #344054;
      font-size: 12px;
    }
    .inside_buy_zone, .below_sponsor_cost {
      background: #e7f5ef;
      color: var(--green);
    }
    .interesting_too_expensive {
      background: #fff2d8;
      color: var(--amber);
    }
    @media (max-width: 820px) {
      body { grid-template-columns: 1fr; }
      aside { position: static; }
      nav { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      main { padding: 18px; overflow-x: auto; }
      table { min-width: 760px; }
    }
    """
