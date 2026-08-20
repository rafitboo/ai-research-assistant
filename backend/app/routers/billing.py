import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sslcommerz_lib import SSLCOMMERZ

from app.database import get_db
from app.models import User, Transaction
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/billing", tags=["Billing & Subscription"])

sslcz = SSLCOMMERZ({
    'store_id': 'testbox', 
    'store_pass': 'qwerty', 
    'issandbox': True 
})

def get_valid_user_id(current_user, db: Session) -> int:
    if hasattr(current_user, 'id') and current_user.id is not None:
        return current_user.id
    if isinstance(current_user, dict) and current_user.get("id") is not None:
        return current_user.get("id")
    email = getattr(current_user, 'email', None) or (isinstance(current_user, dict) and current_user.get("email"))
    if email:
        db_user = db.query(User).filter(User.email == email).first()
        if db_user:
            return db_user.id
    raise HTTPException(status_code=401, detail="Could not resolve valid user ID.")


@router.get("/status")
def get_billing_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    user = db.query(User).filter(User.id == user_id).first()
    transactions = db.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.created_at.desc()).all()
    
    return {
        "tier": user.subscription_tier,
        # Format the date cleanly (e.g., "August 25, 2026")
        "expires_at": user.subscription_expires_at.strftime("%B %d, %Y") if user.subscription_expires_at else None,
        "cancel_at_period_end": bool(user.cancel_at_period_end),
        "history": [
            {
                "id": t.id,
                "amount": t.amount,
                "currency": t.currency,
                "status": t.status,
                "ref": t.transaction_ref,
                "date": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "N/A"
            } for t in transactions
        ]
    }

# --- NEW: Cancel Subscription Endpoint ---
@router.post("/cancel-subscription")
def cancel_subscription(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or user.subscription_tier != "Premium":
        raise HTTPException(status_code=400, detail="You do not have an active premium subscription.")
        
    user.cancel_at_period_end = 1
    db.commit()
    return {"message": "Subscription set to cancel."}


@router.post("/initiate-payment")
def initiate_payment(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    user = db.query(User).filter(User.id == user_id).first()
    
    if user.subscription_tier == "Premium" and not user.cancel_at_period_end:
        raise HTTPException(status_code=400, detail="Already on an active Premium tier.")

    transaction_ref = f"txn_{uuid.uuid4().hex[:12].upper()}"
    
    new_txn = Transaction(
        user_id=user_id, amount=1500.00, currency="BDT", 
        status="Pending", transaction_ref=transaction_ref
    )
    db.add(new_txn)
    db.commit()

    post_body = {}
    post_body['total_amount'] = 1500.00
    post_body['currency'] = "BDT"
    post_body['tran_id'] = transaction_ref
    
    base_url = "http://127.0.0.1:8000"
    post_body['success_url'] = f"{base_url}/api/billing/success"
    post_body['fail_url'] = f"{base_url}/api/billing/fail"
    post_body['cancel_url'] = f"{base_url}/api/billing/cancel"
    
    post_body['cus_name'] = user.name
    post_body['cus_email'] = user.email
    post_body['cus_phone'] = "01700000000"
    post_body['cus_add1'] = "Dhaka"
    post_body['cus_city'] = "Dhaka"
    post_body['cus_country'] = "Bangladesh"
    post_body['shipping_method'] = "NO"
    post_body['multi_card_name'] = ""
    post_body['num_of_item'] = 1
    post_body['product_name'] = "Premium Research AI"
    post_body['product_category'] = "Software Subscriptions"
    post_body['product_profile'] = "general"

    response = sslcz.createSession(post_body)
    
    if 'GatewayPageURL' in response:
        return {"gateway_url": response['GatewayPageURL']}
    else:
        raise HTTPException(status_code=500, detail="Failed to generate payment gateway session.")


@router.post("/success")
def payment_success(tran_id: str = Form(...), db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.transaction_ref == tran_id).first()
    if txn:
        txn.status = "Completed"
        user = db.query(User).filter(User.id == txn.user_id).first()
        if user:
            user.subscription_tier = "Premium"
            # --- UPDATED: Add 30 days to the expiry date & reset cancellation ---
            user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            user.cancel_at_period_end = 0
        db.commit()
    return RedirectResponse(url="http://127.0.0.1:5000/billing?status=success", status_code=303)

@router.post("/fail")
def payment_fail(tran_id: str = Form(...), db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.transaction_ref == tran_id).first()
    if txn:
        txn.status = "Failed"
        db.commit()
    return RedirectResponse(url="http://127.0.0.1:5000/billing?status=fail", status_code=303)

@router.post("/cancel")
def payment_cancel(tran_id: str = Form(...), db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.transaction_ref == tran_id).first()
    if txn:
        txn.status = "Cancelled"
        db.commit()
    return RedirectResponse(url="http://127.0.0.1:5000/billing?status=cancelled", status_code=303)