from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime

app = FastAPI(title="BeanBack API (MVP)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

TX: List[dict] = []  # in-memory demo
CAFES = {"c1": {"name": "Cafe A"}, "c2": {"name": "Cafe B"}, "c3": {"name": "Cafe C"}}

def last_paid_transactions(user_id: str, n: int = 8) -> List[dict]:
    paid = [t for t in TX if t["user_id"] == user_id and not t["is_freebie"]]
    return paid[-n:]

def stamp_balance(user_id: str) -> int:
    paid = sum(1 for t in TX if t["user_id"] == user_id and not t["is_freebie"])
    freebies = sum(8 for t in TX if t["user_id"] == user_id and t["is_freebie"])
    return max(0, paid - freebies)

class EarnIn(BaseModel):
    user_id: str
    cafe_id: str
    amount_cents: int = 0

class RedeemIn(BaseModel):
    user_id: str
    cafe_id: str
    cogs_cents: int = 500

@app.get("/")
def root():
    return {"status":"ok","service":"beanback-api","try":["/health","/docs","/wallet/u1"]}

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

@app.get("/wallet/{user_id}")
def wallet(user_id: str):
    bal = stamp_balance(user_id)
    last10 = [t for t in TX if t["user_id"] == user_id][-10:]
    return {"user_id": user_id, "stamps": bal, "last": last10}

@app.post("/stamps/earn")
def earn(inb: EarnIn):
    if inb.cafe_id not in CAFES:
        raise HTTPException(404, "Unknown cafe")
    TX.append({
        "tx_id": len(TX)+1, "user_id": inb.user_id, "cafe_id": inb.cafe_id,
        "ts": datetime.utcnow().isoformat(), "is_freebie": False, "amount_cents": inb.amount_cents
    })
    return {"stamps_after": stamp_balance(inb.user_id), "tx_id": len(TX)}

@app.post("/stamps/redeem")
def redeem(inb: RedeemIn):
    if stamp_balance(inb.user_id) < 8:
        raise HTTPException(400, "Insufficient stamps")
    TX.append({
        "tx_id": len(TX)+1, "user_id": inb.user_id, "cafe_id": inb.cafe_id,
        "ts": datetime.utcnow().isoformat(), "is_freebie": True, "amount_cents": 0
    })
    last8 = last_paid_transactions(inb.user_id, 8)
    if len(last8) < 8:
        raise HTTPException(400, "Not enough paid transactions to redeem")
    counts: Dict[str, int] = {}
    for t in last8: counts[t["cafe_id"]] = counts.get(t["cafe_id"], 0) + 1
    contributions = []
    for paying_cafe_id, cnt in counts.items():
        share = round(inb.cogs_cents * (cnt/8.0))
        contributions.append({"paying_cafe_id": paying_cafe_id, "share_cents": int(share)})
    return {"stamps_after": stamp_balance(inb.user_id), "receipt": {"funders": contributions}}
