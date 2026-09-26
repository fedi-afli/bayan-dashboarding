from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import credits, pricing
from ..accounts import CurrentUser
from ..config import settings
from ..deps import current_user, payment_provider
from ..payments import PaymentProvider, PaymentProviderError, start_topup

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("")
def overview(user: CurrentUser = Depends(current_user)):
    return {
        "balance": credits.balance(user.account_id),
        "pricing": pricing.describe(),
        "packs": [p.as_dict() for p in credits.PACKS.values()],
        "history": credits.history(user.account_id),
    }


class CheckoutRequest(BaseModel):
    pack: str


@router.post("/checkout")
def checkout(body: CheckoutRequest, user: CurrentUser = Depends(current_user),
             provider: PaymentProvider = Depends(payment_provider)):
    try:
        return start_topup(provider, user.account_id, user.email, body.pack, settings.public_api_url)
    except KeyError:
        raise HTTPException(400, "Unknown credit pack.")
    except PaymentProviderError:
        raise HTTPException(502, "The payment service is unavailable right now. Please try again in a moment.")
