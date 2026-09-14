from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent_runs, products, purchase_orders, scenarios
from app.db.base import Base, SessionLocal, engine
from app.seed_data import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from app.db.models import Product
        if db.query(Product).count() == 0:
            seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="AI Purchasing Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(purchase_orders.router)
app.include_router(agent_runs.router)
app.include_router(scenarios.router)
