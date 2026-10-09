from __future__ import annotations

from stockpicker.models import Alert, AlertType, Opportunity, WatchlistItem, WatchlistState

ACTIONABLE_STATES = {
    WatchlistState.INSIDE_BUY_ZONE,
    WatchlistState.BELOW_SPONSOR_COST,
}


def alerts_from_opportunities(
    opportunities: list[Opportunity],
    existing_watchlist: dict[str, WatchlistItem],
) -> list[Alert]:
    alerts: list[Alert] = []
    for opportunity in opportunities:
        existing = existing_watchlist.get(opportunity.ticker)
        prior = existing.last_price_status if existing else None
        new = opportunity.price_status
        if prior is None:
            alerts.append(
                Alert(
                    alert_type=AlertType.NEW_SIGNAL,
                    ticker=opportunity.ticker,
                    message=(
                        f"{opportunity.ticker} entered the research queue with "
                        f"{opportunity.best_signal.value} and score {opportunity.score:.1f}."
                    ),
                    prior_state=None,
                    new_state=new,
                    severity=2,
                )
            )
        elif prior != new:
            alerts.append(
                Alert(
                    alert_type=AlertType.PRICE_ZONE_CHANGED,
                    ticker=opportunity.ticker,
                    message=f"{opportunity.ticker} moved from {prior.value} to {new.value}.",
                    prior_state=prior,
                    new_state=new,
                    severity=2,
                )
            )

        if new == WatchlistState.BELOW_SPONSOR_COST and prior != new:
            alerts.append(
                Alert(
                    alert_type=AlertType.BELOW_SPONSOR_COST,
                    ticker=opportunity.ticker,
                    message=f"{opportunity.ticker} is below estimated sponsor cost.",
                    prior_state=prior,
                    new_state=new,
                    severity=1,
                )
            )
        elif new == WatchlistState.INSIDE_BUY_ZONE and prior not in ACTIONABLE_STATES:
            alerts.append(
                Alert(
                    alert_type=AlertType.ENTERED_BUY_ZONE,
                    ticker=opportunity.ticker,
                    message=f"{opportunity.ticker} is now inside the estimated buy zone.",
                    prior_state=prior,
                    new_state=new,
                    severity=1,
                )
            )
    return sorted(alerts, key=lambda item: item.severity)


def watchlist_items_from_opportunities(opportunities: list[Opportunity]) -> list[WatchlistItem]:
    return [
        WatchlistItem(
            ticker=opportunity.ticker,
            issuer_name=opportunity.issuer_name,
            state=(
                WatchlistState.NEEDS_UNDERWRITING
                if opportunity.price_status in ACTIONABLE_STATES
                else WatchlistState.MONITOR_ONLY
            ),
            last_price_status=opportunity.price_status,
            opportunity_score=opportunity.score,
        )
        for opportunity in opportunities
    ]
