import pytest
from app.utils import validators


def test_is_valid_name_with_valid_names():
    """Test that valid names are accepted."""
    assert validators.is_valid_name("John Doe")
    assert validators.is_valid_name("Jane")
    assert validators.is_valid_name("Alice Smith")


def test_is_valid_name_with_empty_strings():
    """Test that empty strings are rejected."""
    assert not validators.is_valid_name("")
    assert not validators.is_valid_name("   ")


def test_is_valid_name_with_anonymous():
    """Test that 'anonymous' is rejected."""
    assert not validators.is_valid_name("Anonymous")
    assert not validators.is_valid_name("anonymous")
    assert not validators.is_valid_name("ANONYMOUS")


def test_is_valid_name_with_quoted_strings():
    """Test that quoted strings are properly handled."""
    assert validators.is_valid_name('"John"')
    assert validators.is_valid_name("'Jane'")


def test_is_valid_name_with_no_alphabetic():
    """Test that names without alphabetic characters are rejected."""
    assert not validators.is_valid_name("123")
    assert not validators.is_valid_name("!@#$%")


def test_normalize_event_path_with_prefix():
    """Test that event paths with AOI_ prefix are unchanged."""
    assert validators.normalize_event_path("AOI_test") == "AOI_test"
    assert validators.normalize_event_path("AOI_123") == "AOI_123"


def test_normalize_event_path_without_prefix():
    """Test that event paths without AOI_ prefix get it added."""
    assert validators.normalize_event_path("test") == "AOI_test"
    assert validators.normalize_event_path("123") == "AOI_123"


def test_normalize_phone():
    """Test that phone numbers are normalized correctly."""
    assert validators.normalize_phone("+1-234-567-8900") == "12345678900"
    assert validators.normalize_phone("+1 234 567 8900") == "12345678900"
    assert validators.normalize_phone("1234567890") == "1234567890"
    assert validators.normalize_phone("+44 20 1234 5678") == "442012345678"


def test_norm_with_whitespace():
    """Test that _norm collapses whitespace correctly."""
    assert validators._norm("  hello   world  ") == "hello world"
    assert validators._norm("test\t\nstring") == "test string"


def test_norm_with_case():
    """Test that _norm lowercases strings."""
    assert validators._norm("HELLO WORLD") == "hello world"
    assert validators._norm("MiXeD CaSe") == "mixed case"


def test_norm_with_empty_string():
    """Test that _norm handles empty strings."""
    assert validators._norm("") == ""
    assert validators._norm(None) == ""
