from monsoon_bot.selectors import (
    _xpath_literal,
    retail_space_xpath,
    vendor_buy_xpath,
)


class TestXpathLiteral:
    def test_plain(self):
        assert _xpath_literal("Jakarta") == "'Jakarta'"

    def test_single_quote_uses_double(self):
        assert _xpath_literal("O'Hare") == '"O\'Hare"'

    def test_both_quotes_uses_concat(self):
        result = _xpath_literal("O'\"x")
        assert result.startswith("concat(")
        assert "\"'\"" in result  # the apostrophe is spliced in via concat

    def test_embedded_in_xpath_is_well_formed(self):
        # A name with an apostrophe must not break the surrounding literal.
        xp = retail_space_xpath("O'Hare")
        assert "'O'Hare'" not in xp          # not the naive broken form
        assert '"O\'Hare"' in xp             # safely double-quoted

    def test_vendor_xpath_quotes_safely(self):
        assert '"O\'Brien"' in vendor_buy_xpath("O'Brien")
