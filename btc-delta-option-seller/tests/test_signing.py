import hashlib
import hmac

from bos.exchange.signing import canonical_json, canonical_query, sign_rest, sign_websocket


def test_rest_signature_matches_official_prehash_rule() -> None:
    secret = "secret"
    message = "GET1542110948/v2/orders?product_id=1&state=open"
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    actual = sign_rest(
        secret, "GET", "1542110948", "/v2/orders", "product_id=1&state=open"
    )
    assert actual == expected


def test_websocket_signature_uses_live_path() -> None:
    expected = sign_rest("secret", "GET", "123", "/live")
    assert sign_websocket("secret", "123") == expected


def test_canonical_encoding() -> None:
    assert canonical_query({"state": "open", "empty": None}) == "state=open"
    assert canonical_json({"size": 1, "price": "2"}) == '{"size":1,"price":"2"}'
