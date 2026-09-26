"""
Local stand-in for a real gateway, so the whole top-up flow can be tested
without an account anywhere. It mimics Konnect: a hosted "checkout page",
then the customer's browser is redirected to our notify URL, and the server
verifies by asking the "provider". Only mounted when PAYMENT_PROVIDER=dev.
"""

import html
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from .base import Checkout, ProviderPayment


class DevProvider:
    name = "dev"

    def __init__(self, public_api_url: str):
        self.public_api_url = public_api_url.rstrip("/")
        # provider-side state (in memory: dev only)
        self.payments: dict[str, dict] = {}

    def create_checkout(self, *, payment_id: str, amount_millimes: int, description: str,
                        notify_url: str, customer_email: Optional[str]) -> Checkout:
        ref = "dev_" + uuid.uuid4().hex[:16]
        self.payments[ref] = {"order_id": payment_id, "amount": amount_millimes, "status": "pending",
                              "description": description, "notify_url": notify_url}
        return Checkout(provider_ref=ref, url=f"{self.public_api_url}/payments/dev/checkout/{ref}")

    def fetch_payment(self, provider_ref: str) -> ProviderPayment:
        p = self.payments.get(provider_ref)
        if p is None:
            return ProviderPayment(completed=False, amount_millimes=None, order_id=None)
        return ProviderPayment(completed=p["status"] == "completed", amount_millimes=p["amount"],
                               order_id=p["order_id"], raw=dict(p))

    def router(self) -> APIRouter:
        r = APIRouter(prefix="/payments/dev", include_in_schema=False)

        @r.get("/checkout/{ref}", response_class=HTMLResponse)
        def checkout_page(ref: str):
            p = self.payments.get(ref)
            if p is None:
                raise HTTPException(404, "Unknown dev payment")
            amount = f"{p['amount'] / 1000:.3f} TND"
            return f"""<!doctype html><html><head><meta charset="utf-8"><title>Dev checkout</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:system-ui,sans-serif;background:#f1f5f9;display:flex;justify-content:center;padding:48px 16px">
<div style="background:#fff;border-radius:16px;padding:28px;max-width:380px;width:100%;box-shadow:0 1px 3px rgba(0,0,0,.08)">
<p style="margin:0;font-size:12px;color:#b45309;background:#fef3c7;display:inline-block;padding:2px 8px;border-radius:99px">
Simulated payment — development only</p>
<h1 style="font-size:20px;margin:16px 0 4px">{html.escape(p['description'])}</h1>
<p style="font-size:28px;font-weight:600;margin:8px 0 24px">{amount}</p>
<form method="post" action="/payments/dev/checkout/{ref}/pay">
<button style="width:100%;padding:12px;border:0;border-radius:10px;background:#4f46e5;color:#fff;font-size:15px;cursor:pointer">
Pay {amount}</button></form>
<form method="post" action="/payments/dev/checkout/{ref}/cancel" style="margin-top:8px">
<button style="width:100%;padding:10px;border:0;border-radius:10px;background:#f1f5f9;color:#475569;cursor:pointer">
Cancel</button></form></div></body></html>"""

        @r.post("/checkout/{ref}/pay")
        def pay(ref: str):
            p = self.payments.get(ref)
            if p is None:
                raise HTTPException(404, "Unknown dev payment")
            p["status"] = "completed"
            # like Konnect: send the customer's browser to our notify URL
            return RedirectResponse(f"{p['notify_url']}?payment_ref={ref}", status_code=303)

        @r.post("/checkout/{ref}/cancel")
        def cancel(ref: str):
            p = self.payments.get(ref)
            if p is None:
                raise HTTPException(404, "Unknown dev payment")
            return RedirectResponse(f"{p['notify_url']}?payment_ref={ref}", status_code=303)

        return r
