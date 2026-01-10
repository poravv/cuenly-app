import logging
import asyncio
from datetime import datetime, timedelta
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.pagopar_service import PagoparService
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

async def process_recurring_payments_job():
    """
    Job that runs daily to process recurring payments.
    1. Find due subscriptions (next_billing_date <= now).
    2. For each, charge using stored card token.
    3. If success -> Extend next_billing_date.
    4. If fail -> Log failure, maybe mark status as 'past_due'.
    """
    logger.info("🚀 Starting Recurring Payments Job")
    
    sub_repo = SubscriptionRepository()
    trans_repo = TransactionRepository()
    pagopar_service = PagoparService()
    user_repo = UserRepository()
    
    # 1. Get due subscriptions
    # We need a method in repo for this.
    # Since we didn't implement get_due_subscriptions in the previous step (oops),
    # let's implement the query here or add it to repo.
    # Ideally add to repo, but for speed I will use the collection directly via the repo instance if possible,
    # or better, add the method now.
    
    try:
        now = datetime.utcnow()
        query = {
            "status": "active",
            "next_billing_date": {"$lte": now},
            "pagopar_card_token": {"$exists": True, "$ne": None}
        }
        
        due_subs = list(sub_repo.subscriptions_collection.find(query))
        logger.info(f"📅 Found {len(due_subs)} subscriptions due for payment.")
        
        for sub in due_subs:
            user_email = sub["user_email"]
            amount = sub.get("plan_price", 0)
            sub_id = str(sub["_id"])
            
            if amount <= 0:
                logger.warning(f"⚠️ Subscription {sub_id} has 0 amount. Skipping.")
                continue

            logger.info(f"💸 Processing payment for {user_email} - {amount} {sub.get('currency')}")
            
            try:
                # Get Pagopar User ID
                pagopar_id = user_repo.get_pagopar_user_id(user_email)
                if not pagopar_id:
                    logger.error(f"❌ User {user_email} has no Pagopar ID. Cannot charge.")
                    continue
                    
                card_token = sub["pagopar_card_token"]
                
                # Create Order Hash (Mocked/Standard)
                order_ref = f"sub_{sub_id}_{int(now.timestamp())}"
                order_hash = await pagopar_service.create_order(
                    pagopar_id, 
                    amount, 
                    f"Renovación Suscripción {sub.get('plan_name')}", 
                    order_ref
                )
                
                # Charge
                success = await pagopar_service.process_payment(pagopar_id, order_hash, card_token)
                
                # Log Result
                status = "success" if success else "failed"
                await trans_repo.log_transaction(
                    user_email, amount, sub.get("currency", "PYG"), status, 
                    reference=order_ref, subscription_id=sub_id
                )
                
                if success:
                    # Update Subscription Dates
                    # Calculate new dates
                    current_next = sub.get("next_billing_date") or now
                    
                    if sub.get("billing_period") == "monthly":
                        new_next = current_next + timedelta(days=30)
                    elif sub.get("billing_period") == "yearly":
                        new_next = current_next + timedelta(days=365)
                    else:
                        new_next = current_next + timedelta(days=30) # Default
                        
                    sub_repo.subscriptions_collection.update_one(
                        {"_id": sub["_id"]},
                        {
                            "$set": {
                                "next_billing_date": new_next,
                                "last_payment_date": now,
                                "status": "active" # Ensure active
                            }
                        }
                    )
                    logger.info(f"✅ Payment SUCCESS for {user_email}. Next billing: {new_next}")
                else:
                    logger.warning(f"❌ Payment FAILED for {user_email}.")
                    # Optional: Retry logic or mark as past_due
                    # For now just log.
            
            except Exception as e:
                logger.error(f"❌ Error processing subscription {sub_id}: {e}")

    except Exception as e:
        logger.error(f"❌ Critical error in recurring payments job: {e}")

    logger.info("🏁 Recurring Payments Job Finished")
