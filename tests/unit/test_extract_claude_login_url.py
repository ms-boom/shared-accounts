"""Tests for ValidationService.extract_claude_login_url().

A user sends the single-use magic link wrapped in `code` / ```code block```
so Telegram does not turn it into a clickable link and burn the token before
the bot opens it. Telegram strips the backticks from message.text, so the URL
arrives as plain text — possibly with surrounding whitespace, newlines, other
words, or punctuation clinging to it. Extraction must isolate the URL robustly
and defer to is_claude_login_url() for what counts as a login link.
"""

import pytest

from core.services.validation_service import ValidationService

MAGIC = "https://claude.ai/magic-link#08519fc71ee1d504b701996803c170ed:bmtoken"


@pytest.mark.unit
def test__lone_url__is_extracted() -> None:
    assert ValidationService.extract_claude_login_url(MAGIC) == MAGIC


@pytest.mark.unit
def test__url_wrapped_in_whitespace__is_extracted() -> None:
    # A ```code block``` arrives with leading/trailing newlines.
    assert ValidationService.extract_claude_login_url(f"\n{MAGIC}\n") == MAGIC


@pytest.mark.unit
def test__url_surrounded_by_text__is_extracted() -> None:
    text = f"вот ссылка из письма: {MAGIC} держи"
    assert ValidationService.extract_claude_login_url(text) == MAGIC


@pytest.mark.unit
@pytest.mark.parametrize(
    "wrapper", ["{url}.", "({url})", "<{url}>", '"{url}"', "{url}`"]
)
def test__clinging_punctuation_is_trimmed(wrapper: str) -> None:
    text = wrapper.format(url=MAGIC)
    assert ValidationService.extract_claude_login_url(text) == MAGIC


@pytest.mark.unit
def test__legacy_login_token_url__is_extracted() -> None:
    url = "https://claude.ai/login?token=abc123def456"
    assert ValidationService.extract_claude_login_url(url) == url


@pytest.mark.unit
def test__fragment_is_preserved() -> None:
    # The token lives in the fragment — it must survive extraction intact.
    extracted = ValidationService.extract_claude_login_url(MAGIC)
    assert extracted is not None
    assert extracted.endswith(":bmtoken")


@pytest.mark.unit
def test__picks_login_url_among_other_urls() -> None:
    text = f"смотри https://example.com/foo и {MAGIC}"
    assert ValidationService.extract_claude_login_url(text) == MAGIC


@pytest.mark.unit
def test__no_login_url__returns_none() -> None:
    assert ValidationService.extract_claude_login_url("просто текст без ссылки") is None


@pytest.mark.unit
def test__empty_string__returns_none() -> None:
    assert ValidationService.extract_claude_login_url("") is None


@pytest.mark.unit
def test__non_login_claude_url__returns_none() -> None:
    text = "https://claude.ai/auth/authorize?client_id=test"
    assert ValidationService.extract_claude_login_url(text) is None
