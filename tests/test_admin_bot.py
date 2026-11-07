from app.telegram.bot import AdminBot


class DummySessions:
    pass


def test_admin_id_allowlist_parsing():
    bot = AdminBot("token", "12345, 67890,not-a-number", DummySessions(), None)
    assert bot.admin_ids == {12345, 67890}
    assert bot.configured is True


def test_bot_disabled_without_token_or_admins():
    assert AdminBot("", "12345", DummySessions(), None).configured is False
    assert AdminBot("token", "", DummySessions(), None).configured is False
