"""Баға шекаралары, құпиясөз қауіпсіздігі және енгізу шарттары."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.main import calculate_totals
from backend.schemas import OrderCreate, ProductUpdate, Register
from backend.security import hash_password, token_digest, verify_password


@pytest.mark.parametrize("subtotal,method,promo,discount,fee,total", [
    (18900, "courier", "", 0, 1500, 20400),
    (18900, "pickup", "", 0, 0, 18900),
    (24999, "courier", "", 0, 1500, 26499),
    (25000, "courier", "", 0, 0, 25000),
    (25000, "courier", "GUL10", 2500, 1500, 24000),
    (30000, "courier", "GUL10", 3000, 0, 27000),
    (19999, "pickup", "GUL10", 1999, 0, 18000),
    (1, "pickup", "GUL10", 0, 0, 1),
    (0, "pickup", "", 0, 0, 0),
])
def test_totals_and_delivery_threshold(subtotal, method, promo, discount, fee, total):
    result = calculate_totals(subtotal, method, promo)
    assert result == {"subtotal": subtotal, "discount": discount, "delivery_fee": fee, "total": total}


@pytest.mark.parametrize("subtotal,method,promo", [
    (-1, "pickup", ""), (1.5, "pickup", ""), (True, "pickup", ""),
    (100, "drone", ""), (100, "pickup", "FREE100"),
])
def test_totals_reject_invalid_values(subtotal, method, promo):
    with pytest.raises(ValueError):
        calculate_totals(subtotal, method, promo)


def test_password_hash_accepts_only_original_password():
    password = "ҚұпияСөз!2026"
    hashed = hash_password(password)
    assert password not in hashed
    assert verify_password(password, hashed)
    assert not verify_password("ҚатеСөз!2026", hashed)
    assert not verify_password("", hashed)


def test_password_hashes_have_unique_salts():
    first, second = hash_password("Flower123!"), hash_password("Flower123!")
    assert first != second
    assert verify_password("Flower123!", first)
    assert verify_password("Flower123!", second)


@pytest.mark.parametrize("malformed", ["", "plaintext", "argon2$1$salt$hash", "pbkdf2_sha256$invalid$salt$hash"])
def test_malformed_password_hash_is_rejected(malformed):
    assert verify_password("Flower123!", malformed) is False


def test_session_token_digest_is_stable_but_not_plaintext():
    token = "a-random-client-bearer-token"
    assert token_digest(token) == token_digest(token)
    assert token_digest(token) != token_digest(token + "x")
    assert token not in token_digest(token)
    assert len(token_digest(token)) == 64


@pytest.mark.parametrize("password", ["", "short1", "onlyletters", "1234567890"])
def test_weak_password_is_rejected(password):
    with pytest.raises(ValidationError):
        Register(name="Айдана", email="aidana@example.com", password=password)


def test_signup_cannot_inject_admin_role():
    with pytest.raises(ValidationError):
        Register(name="Айдана", email="aidana@example.com", password="Flower123!", role="admin")


def test_patch_preserves_omitted_fields_and_allows_only_optional_null():
    assert ProductUpdate(price=20000).model_dump(exclude_unset=True) == {"price": 20000}
    assert ProductUpdate(old_price=None).model_dump(exclude_unset=True) == {"old_price": None}
    with pytest.raises(ValidationError):
        ProductUpdate(price=None)


def valid_order():
    today = datetime.now(timezone(timedelta(hours=5))).date()
    return {"items": [{"product_id": 1, "quantity": 1}], "recipient_name": "Айдана",
            "phone": "+77011234567", "address": "Алматы, Абай 10", "delivery_date": today.isoformat()}


def test_past_delivery_date_is_rejected():
    data = valid_order()
    data["delivery_date"] = (datetime.now(timezone(timedelta(hours=5))).date() - timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):
        OrderCreate(**data)


def test_duplicate_items_cannot_bypass_quantity_limit():
    data = valid_order()
    data["items"] = [{"product_id": 1, "quantity": 20}, {"product_id": 1, "quantity": 20}]
    with pytest.raises(ValidationError):
        OrderCreate(**data)


def test_pickup_requires_no_street_address():
    data = valid_order()
    data.update(delivery_method="pickup", address="")
    assert OrderCreate(**data).address == ""
    data["delivery_method"] = "courier"
    with pytest.raises(ValidationError):
        OrderCreate(**data)
