"""Unitarios P0: abonos y sesión."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.auth.session import (
    LEGACY_ADMIN_TOKEN,
    is_admin_session_valid,
    resolve_user_session,
    sign_admin_session,
    sign_user_session,
)
from app.services.payment_service import (
    PaymentValidationError,
    parse_amount,
    validate_payment_amount,
)


def test_parse_amount_valid():
    assert parse_amount("10.5") == Decimal("10.50")
    assert parse_amount("10,50") == Decimal("10.50")


def test_parse_amount_rejects_zero_and_invalid():
    with pytest.raises(PaymentValidationError):
        parse_amount("0")
    with pytest.raises(PaymentValidationError):
        parse_amount("-1")
    with pytest.raises(PaymentValidationError):
        parse_amount("abc")


def test_validate_payment_amount_within_pending():
    q = SimpleNamespace(pending_balance=100)
    validate_payment_amount(q, Decimal("50.00"))


def test_validate_payment_amount_over_pending():
    q = SimpleNamespace(pending_balance=5)
    with pytest.raises(PaymentValidationError) as exc:
        validate_payment_amount(q, Decimal("10.00"))
    assert "saldo pendiente" in str(exc.value).lower()


def test_user_session_roundtrip():
    token = sign_user_session("pytest_user")
    assert resolve_user_session(token) == "pytest_user"


def test_user_session_rejects_forged():
    assert resolve_user_session("not.a.valid.token") is None
    assert resolve_user_session(None) is None


def test_user_session_legacy_plaintext_rejected_by_default():
    assert resolve_user_session("legacy_user") is None


def test_admin_session_valid():
    token = sign_admin_session()
    assert is_admin_session_valid(token) is True
    assert is_admin_session_valid(None) is False
    assert is_admin_session_valid("garbage") is False


def test_admin_legacy_token_rejected_by_default():
    assert is_admin_session_valid(LEGACY_ADMIN_TOKEN) is False
