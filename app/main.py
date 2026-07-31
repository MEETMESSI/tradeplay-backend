from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import engine, Base
load_dotenv()

from app.models import (
    user,
    portfolio,
    position,
    trade,
    watchlist,
    portfolio_snapshot,
)

# import routes
from app.routes import auth, trading, portfolio, market, analytics

# ✅ CREATE APP FIRST
app = FastAPI(title="Tradeplay API")

# ✅ ADD CORS AFTER app is created
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# create tables
Base.metadata.create_all(bind=engine)

# include routes
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(trading.router, prefix="/trade", tags=["Trading"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
app.include_router(market.router, prefix="/market", tags=["Market"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

@app.get("/")
def root():
    return {"message": "Tradeplay backend is running 🚀"}