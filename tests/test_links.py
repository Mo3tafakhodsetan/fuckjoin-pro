import pytest
from app.jobs.worker import parse_message_link

def test_public_message_link():
    assert parse_message_link("https://t.me/examplechannel/123") == ("examplechannel", 123, False)

def test_private_message_link():
    assert parse_message_link("https://t.me/c/123456/789") == ("123456", 789, True)

def test_invite_link():
    assert parse_message_link("https://t.me/+AbCdEfGhIjKl") == ("https://t.me/+AbCdEfGhIjKl", 0, False)

@pytest.mark.parametrize("url", ["https://t.me", "https://evil.test/example/1"])
def test_rejects_non_direct_links(url):
    with pytest.raises(ValueError):
        parse_message_link(url)
