"""Test-only peeks behind the API. Real clients can't do these: invite tokens and seller ids never leave the server."""
from app.main import store


def tokens_of(rfq_id: str) -> dict:
    """supplier_id -> invite token, read straight from the store."""
    return dict(store.rfqs[rfq_id].supplier_tokens)


def alias(rfq_id: str, supplier_id: str) -> str:
    """The "Seller N" a buyer sees for this supplier on this request."""
    return store.alias_for(rfq_id, supplier_id)


def quote(client, rfq_id: str, sid: str, price=10, size=1, freight=200, lead=3, **extra):
    """A seller submits a quote through their invite link."""
    body = {"supplier_name": f"Supplier {sid}", "pack_price": price, "pack_size": size, "freight": freight,
            "lead_days": lead, **extra}
    return client.post(f"/api/rfq-by-token/{tokens_of(rfq_id)[sid]}/quotes", json=body)
