from sqlalchemy.orm import Session

from app.models.trade import Trade


def get_trade_stats(user_id: int, db: Session):

    # =====================================================
    # GET USER TRADES
    # =====================================================

    trades = (
        db.query(Trade)
        .filter(
            Trade.user_id == user_id
        )
        .order_by(
            Trade.created_at.asc()
        )
        .all()
    )


    # =====================================================
    # NO TRADES
    # =====================================================

    if not trades:

        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "realized_pnl": 0,
            "profit_factor": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "largest_win": 0,
            "largest_loss": 0,
            "best_trade": 0,
            "worst_trade": 0,
        }


    # =====================================================
    # CLOSED TRADES
    # =====================================================
    #
    # Realized P&L is generated when a position is closed.
    # Therefore, only trades with a non-zero realized P&L
    # are treated as completed/closed trades here.
    #
    # We also keep non-zero values only to avoid counting
    # BUY trades that have realized_pnl = 0.
    # =====================================================

    closed_trades = [

        trade

        for trade in trades

        if trade.realized_pnl is not None

        and abs(float(trade.realized_pnl)) > 0

    ]


    # =====================================================
    # IF NO CLOSED TRADES
    # =====================================================

    if not closed_trades:

        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "realized_pnl": 0,
            "profit_factor": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "largest_win": 0,
            "largest_loss": 0,
            "best_trade": 0,
            "worst_trade": 0,
        }


    # =====================================================
    # P&L VALUES
    # =====================================================

    pnl_values = [

        float(trade.realized_pnl)

        for trade in closed_trades

        if trade.realized_pnl is not None

    ]


    # =====================================================
    # WINNING / LOSING TRADES
    # =====================================================

    winning_trades = [

        pnl

        for pnl in pnl_values

        if pnl > 0

    ]


    losing_trades = [

        pnl

        for pnl in pnl_values

        if pnl < 0

    ]


    # =====================================================
    # BASIC STATISTICS
    # =====================================================

    total_trades = len(pnl_values)

    winning_count = len(winning_trades)

    losing_count = len(losing_trades)


    win_rate = (

        winning_count / total_trades * 100

        if total_trades > 0

        else 0

    )


    realized_pnl = sum(pnl_values)


    # =====================================================
    # PROFIT FACTOR
    # =====================================================
    #
    # Profit Factor =
    # Gross Profits / Gross Losses
    # =====================================================

    gross_profit = sum(winning_trades)

    gross_loss = abs(
        sum(losing_trades)
    )


    if gross_loss > 0:

        profit_factor = (
            gross_profit / gross_loss
        )

    elif gross_profit > 0:

        profit_factor = float("inf")

    else:

        profit_factor = 0


    # =====================================================
    # AVERAGES
    # =====================================================

    avg_win = (

        gross_profit / winning_count

        if winning_count > 0

        else 0

    )


    avg_loss = (

        sum(losing_trades) / losing_count

        if losing_count > 0

        else 0

    )


    # =====================================================
    # RECORDS
    # =====================================================

    largest_win = (

        max(winning_trades)

        if winning_trades

        else 0

    )


    largest_loss = (

        min(losing_trades)

        if losing_trades

        else 0

    )


    best_trade = max(pnl_values)

    worst_trade = min(pnl_values)


    # =====================================================
    # RETURN
    # =====================================================

    return {

        "total_trades": total_trades,

        "winning_trades": winning_count,

        "losing_trades": losing_count,

        "win_rate": round(
            win_rate,
            2
        ),

        "realized_pnl": round(
            realized_pnl,
            2
        ),

        "profit_factor": (
            round(
                profit_factor,
                2
            )
            if profit_factor != float("inf")
            else 999.99
        ),

        "avg_win": round(
            avg_win,
            2
        ),

        "avg_loss": round(
            avg_loss,
            2
        ),

        "largest_win": round(
            largest_win,
            2
        ),

        "largest_loss": round(
            largest_loss,
            2
        ),

        "best_trade": round(
            best_trade,
            2
        ),

        "worst_trade": round(
            worst_trade,
            2
        ),

    }