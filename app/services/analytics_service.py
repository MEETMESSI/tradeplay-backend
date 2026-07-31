from sqlalchemy.orm import Session
from app.models.trade import Trade


def get_trade_stats(user_id: int, db: Session):
    sells = (
        db.query(Trade)
        .filter(
            Trade.user_id == user_id,
            Trade.side == "SELL"
        )
        .all()
    )

    total_trades = len(sells)

    wins = [t.realized_pnl for t in sells if t.realized_pnl > 0]
    losses = [t.realized_pnl for t in sells if t.realized_pnl < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "total_trades": total_trades,
        "winning_trades": len(wins),
        "losing_trades": len(losses),

        "win_rate": round(
            (len(wins) / total_trades) * 100,
            2
        ) if total_trades else 0,

        "realized_pnl": round(
            gross_profit + sum(losses),
            2
        ),

        "avg_win": round(
            gross_profit / len(wins),
            2
        ) if wins else 0,

        "avg_loss": round(
            abs(sum(losses)) / len(losses),
            2
        ) if losses else 0,

        "largest_win": round(
            max(wins),
            2
        ) if wins else 0,

        "largest_loss": round(
            abs(min(losses)),
            2
        ) if losses else 0,

        "best_trade": round(
            max([t.realized_pnl for t in sells], default=0),
            2
        ),

        "worst_trade": round(
            min([t.realized_pnl for t in sells], default=0),
            2
        ),

        "profit_factor": round(
            gross_profit / gross_loss,
            2
        ) if gross_loss else 0
    }