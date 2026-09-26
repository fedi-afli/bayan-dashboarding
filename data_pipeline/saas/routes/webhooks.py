from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from ..config import settings
from ..deps import payment_provider
from ..payments import PaymentProvider, PaymentProviderError, handle_notification

router = APIRouter(tags=["payments"], include_in_schema=False)


@router.get("/webhooks/{provider_name}")
def payment_notification(provider_name: str, payment_ref: str = Query(..., max_length=128),
                         provider: PaymentProvider = Depends(payment_provider)):
    """
    Called by the payment provider (Konnect redirects the customer's browser
    here after checkout). Unauthenticated by design — handle_notification()
    re-checks everything with the provider before crediting anything.
    Always ends by sending the browser back to the credits page.
    """
    if provider_name != provider.name:
        raise HTTPException(404)
    try:
        payment_id, outcome = handle_notification(provider, payment_ref)
    except PaymentProviderError:
        payment_id, outcome = None, "error"
    query = urlencode({k: v for k, v in {"payment": payment_id, "status": outcome}.items() if v})
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/credits?{query}", status_code=303)
