import asyncio

from app.db.database import SessionLocal
from app.models.order import Order
from app.services.order_service import check_pending_orders


CHECK_INTERVAL = 60


async def pending_order_worker():

    while True:

        db = SessionLocal()

        try:

            print(
                "[ORDER WORKER] Checking pending orders..."
            )

            user_ids = (
                db.query(Order.user_id)
                .filter(
                    Order.status == "PENDING",
                    Order.order_type == "LIMIT",
                )
                .distinct()
                .all()
            )

            print(
                f"[ORDER WORKER] "
                f"Users with pending orders: "
                f"{len(user_ids)}"
            )

            for (user_id,) in user_ids:

                try:

                    pending_count = (
                        db.query(Order)
                        .filter(
                            Order.user_id == user_id,
                            Order.status == "PENDING",
                            Order.order_type == "LIMIT",
                        )
                        .count()
                    )

                    print(
                        f"[ORDER WORKER] "
                        f"User {user_id}: "
                        f"{pending_count} pending order(s)"
                    )

                    results = check_pending_orders(
                        user_id,
                        db,
                    )

                    if results:

                        print(
                            f"[ORDER WORKER] "
                            f"Filled {len(results)} order(s)"
                        )

                        for result in results:

                            print(
                                f"[ORDER WORKER] "
                                f"{result['symbol']} "
                                f"{result['side']} "
                                f"→ FILLED at "
                                f"${result['filled_price']}"
                            )

                    else:

                        print(
                            f"[ORDER WORKER] "
                            f"User {user_id}: "
                            f"No orders triggered"
                        )

                except Exception as e:

                    print(
                        f"[ORDER WORKER ERROR] "
                        f"User {user_id}: {e}"
                    )

        except Exception as e:

            print(
                f"[ORDER WORKER ERROR]: {e}"
            )

        finally:

            db.close()

        await asyncio.sleep(
            CHECK_INTERVAL
        )