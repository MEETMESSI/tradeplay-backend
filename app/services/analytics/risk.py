import math
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.portfolio_snapshot import PortfolioSnapshot


def get_risk_metrics(
    user_id: int,
    db: Session
):
    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(
            PortfolioSnapshot.user_id == user_id
        )
        .order_by(
            PortfolioSnapshot.created_at.asc()
        )
        .all()
    )

    # -----------------------------------------------------
    # NOT ENOUGH DATA
    # -----------------------------------------------------

    if len(snapshots) < 2:
        return {
            "volatility": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "data_points": len(snapshots),
        }

    # -----------------------------------------------------
    # CLEAN SNAPSHOT DATA
    # -----------------------------------------------------

    history = []

    for snapshot in snapshots:

        value = float(
            snapshot.total_value or 0
        )

        if value <= 0:
            continue

        history.append({
            "date": snapshot.created_at,
            "value": value,
        })

    if len(history) < 2:
        return {
            "volatility": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "data_points": len(history),
        }

    # -----------------------------------------------------
    # RETURNS
    # -----------------------------------------------------

    returns = []

    intervals = []

    for i in range(1, len(history)):

        previous = history[i - 1]
        current = history[i]

        previous_value = previous["value"]
        current_value = current["value"]

        if previous_value <= 0:
            continue

        period_return = (
            current_value - previous_value
        ) / previous_value

        returns.append(period_return)

        elapsed_seconds = (
            current["date"] -
            previous["date"]
        ).total_seconds()

        elapsed_days = (
            elapsed_seconds / 86400
        )

        if elapsed_days > 0:
            intervals.append(
                elapsed_days
            )

    if not returns:
        return {
            "volatility": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "data_points": len(history),
        }

    # -----------------------------------------------------
    # AVERAGE OBSERVATION PERIOD
    # -----------------------------------------------------

    if intervals:
        average_days = (
            sum(intervals) /
            len(intervals)
        )
    else:
        average_days = 1

    # Prevent unrealistic annualisation if multiple
    # snapshots happen within a very short period.
    average_days = max(
        average_days,
        1 / 24
    )

    periods_per_year = (
        365 / average_days
    )

    # -----------------------------------------------------
    # MEAN RETURN
    # -----------------------------------------------------

    mean_return = (
        sum(returns) /
        len(returns)
    )

    # -----------------------------------------------------
    # STANDARD DEVIATION
    # -----------------------------------------------------

    if len(returns) > 1:

        variance = sum(
            (r - mean_return) ** 2
            for r in returns
        ) / (len(returns) - 1)

        standard_deviation = math.sqrt(
            variance
        )

    else:
        standard_deviation = 0

    # -----------------------------------------------------
    # ANNUALIZED VOLATILITY
    # -----------------------------------------------------

    annualized_volatility = (
        standard_deviation *
        math.sqrt(periods_per_year)
    )

    # -----------------------------------------------------
    # ANNUALIZED RETURN
    # -----------------------------------------------------

    first_value = history[0]["value"]
    last_value = history[-1]["value"]

    total_days = (
        history[-1]["date"] -
        history[0]["date"]
    ).total_seconds() / 86400

    if total_days > 0 and first_value > 0:

        annualized_return = (
            (last_value / first_value)
            ** (365 / total_days)
        ) - 1

    else:

        annualized_return = mean_return * periods_per_year

    # -----------------------------------------------------
    # SHARPE RATIO
    # -----------------------------------------------------
    #
    # MVP assumption:
    # Risk-free rate = 0%
    #
    # This can later become configurable.
    # -----------------------------------------------------

    risk_free_rate = 0.0

    if annualized_volatility > 0:

        sharpe_ratio = (
            annualized_return -
            risk_free_rate
        ) / annualized_volatility

    else:

        sharpe_ratio = 0

    # -----------------------------------------------------
    # MAX DRAWDOWN
    # -----------------------------------------------------

    peak = history[0]["value"]

    max_drawdown = 0

    for snapshot in history:

        value = snapshot["value"]

        if value > peak:
            peak = value

        if peak > 0:

            drawdown = (
                value - peak
            ) / peak

            if drawdown < max_drawdown:
                max_drawdown = drawdown

    # -----------------------------------------------------
    # RETURN
    # -----------------------------------------------------

    return {
        "volatility": round(
            annualized_volatility * 100,
            2
        ),

        "sharpe_ratio": round(
            sharpe_ratio,
            2
        ),

        "max_drawdown": round(
            abs(max_drawdown) * 100,
            2
        ),

        "data_points": len(history),

        "risk_free_rate": 0,
    }