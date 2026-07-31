import os

base = "app"

files = {

    f"{base}/core/dependencies.py": """from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.user import User
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    email = decode_access_token(token)

    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
""",

    f"{base}/routes/trading.py": """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.portfolio import Portfolio
from app.models.position import Position
from app.models.trade import Trade
from app.schemas.trade import TradeCreate
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/trade")
def execute_trade(
    trade: TradeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.id

    portfolio = db.query(Portfolio).filter(Portfolio.user_id == user_id).first()

    if not portfolio:
        portfolio = Portfolio(user_id=user_id)
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)

    cost = trade.quantity * trade.price

    if trade.side == "BUY":
        if portfolio.balance < cost:
            raise HTTPException(status_code=400, detail="Not enough balance")

        portfolio.balance -= cost

        position = db.query(Position).filter(
            Position.user_id == user_id,
            Position.symbol == trade.symbol
        ).first()

        if position:
            total_qty = position.quantity + trade.quantity
            position.avg_price = (
                (position.avg_price * position.quantity + cost) / total_qty
            )
            position.quantity = total_qty
        else:
            position = Position(
                user_id=user_id,
                symbol=trade.symbol,
                quantity=trade.quantity,
                avg_price=trade.price
            )
            db.add(position)

    elif trade.side == "SELL":
        position = db.query(Position).filter(
            Position.user_id == user_id,
            Position.symbol == trade.symbol
        ).first()

        if not position or position.quantity < trade.quantity:
            raise HTTPException(status_code=400, detail="Not enough shares")

        portfolio.balance += cost
        position.quantity -= trade.quantity

        if position.quantity == 0:
            db.delete(position)

    else:
        raise HTTPException(status_code=400, detail="Invalid trade type")

    new_trade = Trade(
        user_id=user_id,
        symbol=trade.symbol,
        quantity=trade.quantity,
        price=trade.price,
        side=trade.side
    )

    db.add(new_trade)
    db.commit()

    return {"message": "Trade executed successfully"}
"""
}

# UPDATE security.py (append decode function)
security_file = f"{base}/core/security.py"

decode_function = """

from jose import JWTError

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
"""

# Create folders if missing
for path in files:
    os.makedirs(os.path.dirname(path), exist_ok=True)

# Write new files
for path, content in files.items():
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# Append decode function safely
if os.path.exists(security_file):
    with open(security_file, "r", encoding="utf-8") as f:
        existing = f.read()

    if "decode_access_token" not in existing:
        with open(security_file, "a", encoding="utf-8") as f:
            f.write(decode_function)

print("✅ JWT authentication system added successfully!")