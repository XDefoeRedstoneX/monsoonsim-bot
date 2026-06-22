from monsoon_bot.driver import ActionResult


def test_ok_is_truthy():
    assert ActionResult(True, "done")
    assert bool(ActionResult(True, "done")) is True


def test_failure_is_falsy():
    assert not ActionResult(False, "SKIPPED: nope")
    assert bool(ActionResult(False, "SKIPPED: nope")) is False


def test_message_preserved():
    r = ActionResult(False, "SKIPPED Jakarta: not found")
    assert r.message == "SKIPPED Jakarta: not found"
