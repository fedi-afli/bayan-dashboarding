"""
Konnect (konnect.network) — Tunisian payment gateway, licensed by the BCT.
Accepts Tunisian cards, e-Dinar, Konnect wallet and international cards.

Flow (docs.konnect.network):
  1. POST /payments/init-payment  -> {payUrl, paymentRef}; we send the user to payUrl
  2. After paying, Konnect calls our `webhook` URL with ?payment_ref=... (GET, unsigned —
     and by default it's the customer's browser that is redirected there)
  3. We never trust that call: GET /payments/{paymentRef} with our API key and only
     credit when payment.status == "completed" and amount/orderId match.
Amounts are in millimes for TND.
"""

from typing import Optional

import httpx

from .base import Checkout, PaymentProviderError, ProviderPayment


class KonnectProvider:
    name = "konnect"

    def __init__(self, api_base: str, api_key: str, wallet_id: str, http: Optional[httpx.Client] = None):
        if not api_key or not wallet_id:
            raise ValueError("KONNECT_API_KEY and KONNECT_WALLET_ID must be set to use Konnect")
        self.api_base = api_base.rstrip("/")
        self.http = http or httpx.Client(timeout=15)
        self.headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        self.wallet_id = wallet_id

    def create_checkout(self, *, payment_id: str, amount_millimes: int, description: str,
                        notify_url: str, customer_email: Optional[str]) -> Checkout:
        body = {
            "receiverWalletId": self.wallet_id,
            "token": "TND",
            "amount": amount_millimes,
            "type": "immediate",
            "description": description,
            "acceptedPaymentMethods": ["wallet", "bank_card", "e-DINAR"],
            "lifespan": 30,
            "checkoutForm": False,
            "addPaymentFeesToAmount": False,
            "orderId": payment_id,
            "webhook": notify_url,
            "theme": "light",
        }
        if customer_email:
            body["email"] = customer_email
        try:
            r = self.http.post(f"{self.api_base}/payments/init-payment", json=body, headers=self.headers)
            r.raise_for_status()
            data = r.json()
            return Checkout(provider_ref=data["paymentRef"], url=data["payUrl"])
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise PaymentProviderError(f"Konnect init-payment failed: {e}")

    def fetch_payment(self, provider_ref: str) -> ProviderPayment:
        try:
            r = self.http.get(f"{self.api_base}/payments/{provider_ref}", headers=self.headers)
            r.raise_for_status()
            p = r.json()["payment"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise PaymentProviderError(f"Konnect payment lookup failed: {e}")
        # rely on the payment status, not individual transactions (Konnect docs)
        return ProviderPayment(
            completed=p.get("status") == "completed",
            amount_millimes=p.get("amount"),
            order_id=p.get("orderId"),
            raw=p,
        )
