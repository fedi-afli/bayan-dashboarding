from fastapi import APIRouter, Depends

from .. import pricing
from ..accounts import CurrentUser, get_account
from ..deps import current_user

router = APIRouter(tags=["account"])


@router.get("/me")
def me(user: CurrentUser = Depends(current_user)):
    account = get_account(user.account_id)
    return {
        "user": {"id": user.user_id, "email": user.email, "name": user.name},
        "account": {"id": account["id"], "name": account["name"], "credit_balance": account["credit_balance"]},
        "pricing": pricing.describe(),
    }
