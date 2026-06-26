"""Resend audience sync tests (mocked HTTP)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from src.newsletter import resend_contacts


def test_add_contact_noop_without_audience():
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}, clear=False):
        os.environ.pop("RESEND_AUDIENCE_ID", None)
        assert resend_contacts.add_contact("a@b.com", "tok") is False


def test_add_contact_success():
    mock_resp = MagicMock(status_code=201)
    with patch.dict(
        os.environ,
        {"RESEND_API_KEY": "re_test", "RESEND_AUDIENCE_ID": "aud_123"},
        clear=False,
    ):
        with patch("httpx.post", return_value=mock_resp):
            assert resend_contacts.add_contact("a@b.com", "tok123") is True
