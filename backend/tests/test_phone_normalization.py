"""
Tests for phone number normalization
"""
import pytest
from backend.services.api_service.main import normalize_phone


class TestPhoneNormalization:
    """Test phone number normalization function"""

    def test_normalize_none(self):
        """Test that None returns None"""
        assert normalize_phone(None) is None

    def test_normalize_empty_string(self):
        """Test that empty string returns None"""
        assert normalize_phone("") is None
        assert normalize_phone("   ") is None

    def test_normalize_digits_only(self):
        """Test that plain digits pass through"""
        assert normalize_phone("9702310576") == "9702310576"
        assert normalize_phone("3368296382") == "3368296382"

    def test_normalize_with_dashes(self):
        """Test normalization of phone with dashes"""
        assert normalize_phone("970-231-0576") == "9702310576"
        assert normalize_phone("336-829-6382") == "3368296382"

    def test_normalize_with_parentheses(self):
        """Test normalization of phone with parentheses"""
        assert normalize_phone("(970) 231-0576") == "9702310576"
        assert normalize_phone("(336) 829-6382") == "3368296382"

    def test_normalize_with_spaces(self):
        """Test normalization of phone with spaces"""
        assert normalize_phone("970 231 0576") == "9702310576"
        assert normalize_phone("336 829 6382") == "3368296382"

    def test_normalize_international_format(self):
        """Test normalization of international format (strips leading 1 for US)"""
        assert normalize_phone("+13368296382") == "3368296382"
        assert normalize_phone("+1 336 829 6382") == "3368296382"
        assert normalize_phone("+1-336-829-6382") == "3368296382"
        assert normalize_phone("1-970-231-0576") == "9702310576"

    def test_normalize_with_dots(self):
        """Test normalization of phone with dots"""
        assert normalize_phone("970.231.0576") == "9702310576"

    def test_normalize_mixed_formatting(self):
        """Test normalization of mixed formatting"""
        assert normalize_phone("+1 (336) 829-6382") == "3368296382"
        assert normalize_phone("1 (970) 231-0576") == "9702310576"

    def test_normalize_with_extension(self):
        """Test normalization of phone with extension (ignores extension)"""
        assert normalize_phone("970-231-0576 ext 123") == "9702310576"
        assert normalize_phone("(970) 231-0576 x123") == "9702310576"

    def test_normalize_only_symbols(self):
        """Test that string with only symbols returns None"""
        assert normalize_phone("---") is None
        assert normalize_phone("() -") is None

    def test_normalize_whitespace_trimmed(self):
        """Test that leading/trailing whitespace is handled"""
        assert normalize_phone("  9702310576  ") == "9702310576"
        assert normalize_phone("  970-231-0576  ") == "9702310576"
