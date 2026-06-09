import pytest

from monsoon_bot.parsing import parse_day, parse_space, parse_stock


class TestParseDay:
    def test_basic(self):
        assert parse_day("12 / 30") == (12, 30)

    def test_no_spaces(self):
        assert parse_day("5/30") == (5, 30)

    def test_with_surrounding_text(self):
        assert parse_day("Day 7 / 28 remaining") == (7, 28)

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_day("no numbers here")


class TestParseSpace:
    def test_with_commas_and_unit(self):
        assert parse_space("1,234 / 5,000 m²") == (1234, 5000)

    def test_plain(self):
        assert parse_space("10 / 200") == (10, 200)

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_space("full")


class TestParseStock:
    def test_with_commas(self):
        assert parse_stock("12,000") == 12000

    def test_zero(self):
        assert parse_stock("0") == 0

    def test_whitespace(self):
        assert parse_stock("  3,500  ") == 3500

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_stock("n/a")
