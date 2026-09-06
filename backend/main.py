from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.connection import get_db

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok", "project": "pr-risk-analysis-platform"}

@app.get("/health/db")
def health_check_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"database": "connected"}