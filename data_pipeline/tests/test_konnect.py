import json

import httpx

from saas.payments.konnect import KonnectProvider


def provider(handler):
    return KonnectProvider("https://api.sandbox.konnect.network/api/v2", "key-123", "wallet-9",
                           http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_create_checkout_sends_documented_fields():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"payUrl": "https://pay.test/x", "paymentRef": "ref-1"})

    checkout = provider(handler).create_checkout(payment_id="pay-1", amount_millimes=25_000,
                                                 description="30 credits", notify_url="https://api.test/webhooks/konnect",
                                                 customer_email="a@b.tn")
    assert checkout.provider_ref == "ref-1" and checkout.url == "https://pay.test/x"
    assert seen["url"].endswith("/payments/init-payment") and seen["key"] == "key-123"
    body = seen["body"]
    assert body["receiverWalletId"] == "wallet-9" and body["amount"] == 25_000 and body["token"] == "TND"
    assert body["orderId"] == "pay-1" and body["webhook"] == "https://api.test/webhooks/konnect"


def test_fetch_payment_reads_payment_status():
    def handler(request):
        assert request.url.path.endswith("/payments/ref-1")
        return httpx.Response(200, json={"payment": {"id": "ref-1", "status": "completed",
                                                     "amount": 25_000, "orderId": "pay-1", "transactions": []}})

    p = provider(handler).fetch_payment("ref-1")
    assert p.completed and p.amount_millimes == 25_000 and p.order_id == "pay-1"


def test_pending_is_not_completed():
    p = provider(lambda r: httpx.Response(200, json={"payment": {"status": "pending", "amount": 1, "orderId": "x"}}))
    assert not p.fetch_payment("ref").completed
