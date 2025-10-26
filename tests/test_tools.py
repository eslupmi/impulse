"""
Unit tests for app.tools module.
"""
import pytest
import yaml

from app.tools import NoAliasDumper, HTMLTextExtractor


class TestNoAliasDumper:
    """Test cases for NoAliasDumper class."""

    def test_no_alias_dumper_initialization(self):
        """Test NoAliasDumper initialization."""
        # NoAliasDumper requires a stream parameter for initialization
        # This is typically used with yaml.dump() which handles the stream
        dumper = NoAliasDumper(None)  # Pass None as stream for testing

        assert dumper is not None
        assert hasattr(dumper, 'ignore_aliases')

    def test_no_alias_dumper_ignore_aliases(self):
        """Test NoAliasDumper ignore_aliases method."""
        dumper = NoAliasDumper(None)

        # Test with various data types - should always return True
        assert dumper.ignore_aliases(None) is True
        assert dumper.ignore_aliases("string") is True
        assert dumper.ignore_aliases(123) is True
        assert dumper.ignore_aliases(123.45) is True
        assert dumper.ignore_aliases(True) is True
        assert dumper.ignore_aliases(False) is True
        assert dumper.ignore_aliases([]) is True
        assert dumper.ignore_aliases({}) is True
        assert dumper.ignore_aliases([1, 2, 3]) is True
        assert dumper.ignore_aliases({"key": "value"}) is True

    def test_no_alias_dumper_with_yaml_dump(self):
        """Test NoAliasDumper with yaml.dump."""
        data = {
            'key1': 'value1',
            'key2': 'value2',
            'nested': {
                'inner_key': 'inner_value'
            }
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'key1' in result
        assert 'value1' in result
        assert 'key2' in result
        assert 'value2' in result
        assert 'nested' in result
        assert 'inner_key' in result
        assert 'inner_value' in result

    def test_no_alias_dumper_with_complex_data(self):
        """Test NoAliasDumper with complex data structures."""
        data = {
            'list': [1, 2, 3, {'nested': 'value'}],
            'dict': {'key': 'value', 'another_key': 'another_value'},
            'mixed': [1, 'string', True, None, {'key': 'value'}]
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'list' in result
        assert 'dict' in result
        assert 'mixed' in result

    def test_no_alias_dumper_with_none_values(self):
        """Test NoAliasDumper with None values."""
        data = {
            'key1': None,
            'key2': 'value',
            'key3': None
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'key1' in result
        assert 'key2' in result
        assert 'key3' in result

    def test_no_alias_dumper_with_empty_values(self):
        """Test NoAliasDumper with empty values."""
        data = {
            'key1': '',
            'key2': [],
            'key3': {},
            'key4': 'value'
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'key1' in result
        assert 'key2' in result
        assert 'key3' in result
        assert 'key4' in result

    def test_no_alias_dumper_with_boolean_values(self):
        """Test NoAliasDumper with boolean values."""
        data = {
            'true_value': True,
            'false_value': False,
            'string_value': 'test'
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'true_value' in result
        assert 'false_value' in result
        assert 'string_value' in result

    def test_no_alias_dumper_with_numeric_values(self):
        """Test NoAliasDumper with numeric values."""
        data = {
            'int_value': 123,
            'float_value': 123.45,
            'negative_int': -123,
            'negative_float': -123.45
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'int_value' in result
        assert 'float_value' in result
        assert 'negative_int' in result
        assert 'negative_float' in result

    def test_no_alias_dumper_with_special_characters(self):
        """Test NoAliasDumper with special characters."""
        data = {
            'special_chars': '!@#$%^&*()_+-=[]{}|;:,.<>?',
            'unicode_chars': '测试',
            'emoji': '🚨'
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'special_chars' in result
        assert 'unicode_chars' in result
        assert 'emoji' in result

    def test_no_alias_dumper_with_whitespace(self):
        """Test NoAliasDumper with whitespace."""
        data = {
            'leading_space': '  value',
            'trailing_space': 'value  ',
            'both_spaces': '  value  ',
            'tabs': '\tvalue\t',
            'newlines': 'value\nwith\nnewlines'
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'leading_space' in result
        assert 'trailing_space' in result
        assert 'both_spaces' in result
        assert 'tabs' in result
        assert 'newlines' in result

    def test_no_alias_dumper_with_quotes(self):
        """Test NoAliasDumper with quotes."""
        data = {
            'single_quotes': "value with 'single' quotes",
            'double_quotes': 'value with "double" quotes',
            'mixed_quotes': 'value with "mixed" and \'quotes\''
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'single_quotes' in result
        assert 'double_quotes' in result
        assert 'mixed_quotes' in result

    def test_no_alias_dumper_with_very_long_strings(self):
        """Test NoAliasDumper with very long strings."""
        long_string = 'a' * 10000
        data = {
            'long_string': long_string,
            'normal_string': 'normal'
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'long_string' in result
        assert 'normal_string' in result

    def test_no_alias_dumper_with_very_deep_nesting(self):
        """Test NoAliasDumper with very deep nesting."""
        data = {'level1': {'level2': {'level3': {'level4': {'level5': 'deep_value'}}}}}

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'level1' in result
        assert 'level2' in result
        assert 'level3' in result
        assert 'level4' in result
        assert 'level5' in result
        assert 'deep_value' in result

    def test_no_alias_dumper_with_large_lists(self):
        """Test NoAliasDumper with large lists."""
        large_list = list(range(1000))
        data = {
            'large_list': large_list,
            'normal_list': [1, 2, 3]
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'large_list' in result
        assert 'normal_list' in result

    def test_no_alias_dumper_with_large_dicts(self):
        """Test NoAliasDumper with large dictionaries."""
        large_dict = {f'key{i}': f'value{i}' for i in range(1000)}
        data = {
            'large_dict': large_dict,
            'normal_dict': {'key': 'value'}
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'large_dict' in result
        assert 'normal_dict' in result

    def test_no_alias_dumper_with_mixed_types(self):
        """Test NoAliasDumper with mixed types."""
        data = {
            'string': 'value',
            'int': 123,
            'float': 123.45,
            'bool': True,
            'none': None,
            'list': [1, 2, 3],
            'dict': {'key': 'value'}
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'string' in result
        assert 'int' in result
        assert 'float' in result
        assert 'bool' in result
        assert 'none' in result
        assert 'list' in result
        assert 'dict' in result

    def test_no_alias_dumper_with_circular_references(self):
        """Test NoAliasDumper with circular references."""
        data = {}
        data['self'] = data  # Circular reference

        # Should raise RecursionError due to circular reference
        with pytest.raises(RecursionError):
            yaml.dump(data, Dumper=NoAliasDumper)

    def test_no_alias_dumper_with_custom_objects(self):
        """Test NoAliasDumper with custom objects."""

        class CustomObject:
            def __init__(self, value):
                self.value = value

        custom_obj = CustomObject('test')
        data = {
            'custom': custom_obj,
            'normal': 'value'
        }

        result = yaml.dump(data, Dumper=NoAliasDumper)

        assert isinstance(result, str)
        assert 'custom' in result
        assert 'normal' in result


class TestHTMLTextExtractor:
    """Test cases for HTMLTextExtractor class."""

    def test_html_text_extractor_initialization(self):
        """Test HTMLTextExtractor initialization."""
        extractor = HTMLTextExtractor()

        assert extractor is not None
        assert extractor.text_parts == []
        assert extractor.in_br is False

    def test_html_text_extractor_simple_text(self):
        """Test HTMLTextExtractor with simple text."""
        extractor = HTMLTextExtractor()
        html = "Simple text content"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Simple text content"

    def test_html_text_extractor_with_tags(self):
        """Test HTMLTextExtractor with HTML tags."""
        extractor = HTMLTextExtractor()
        html = "<p>This is a paragraph</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "This is a paragraph\n"

    def test_html_text_extractor_with_multiple_tags(self):
        """Test HTMLTextExtractor with multiple HTML tags."""
        extractor = HTMLTextExtractor()
        html = "<div><p>Paragraph 1</p><p>Paragraph 2</p></div>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Paragraph 1\nParagraph 2\n"

    def test_html_text_extractor_with_br_tags(self):
        """Test HTMLTextExtractor with br tags."""
        extractor = HTMLTextExtractor()
        html = "Line 1<br>Line 2<br/>Line 3"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Line 1\nLine 2\nLine 3"

    def test_html_text_extractor_with_nested_tags(self):
        """Test HTMLTextExtractor with nested HTML tags."""
        extractor = HTMLTextExtractor()
        html = "<div><p><span>Nested text</span></p></div>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Nested text\n"

    def test_html_text_extractor_with_attributes(self):
        """Test HTMLTextExtractor with HTML attributes."""
        extractor = HTMLTextExtractor()
        html = '<p class="test" id="paragraph">Text with attributes</p>'

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Text with attributes\n"

    def test_html_text_extractor_with_self_closing_tags(self):
        """Test HTMLTextExtractor with self-closing tags."""
        extractor = HTMLTextExtractor()
        html = "Text before<br/>Text after"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Text before\nText after"

    def test_html_text_extractor_with_empty_tags(self):
        """Test HTMLTextExtractor with empty HTML tags."""
        extractor = HTMLTextExtractor()
        html = "<p></p><div></div>"

        extractor.feed(html)
        result = extractor.get_text()

        # Empty tags result in empty string
        assert result == ""

    def test_html_text_extractor_with_whitespace(self):
        """Test HTMLTextExtractor with whitespace."""
        extractor = HTMLTextExtractor()
        html = "  Text with   spaces  "

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "  Text with   spaces  "

    def test_html_text_extractor_with_newlines(self):
        """Test HTMLTextExtractor with newlines."""
        extractor = HTMLTextExtractor()
        html = "Line 1\nLine 2\nLine 3"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Line 1\nLine 2\nLine 3"

    def test_html_text_extractor_with_tabs(self):
        """Test HTMLTextExtractor with tabs."""
        extractor = HTMLTextExtractor()
        html = "Text\twith\ttabs"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Text\twith\ttabs"

    def test_html_text_extractor_with_special_characters(self):
        """Test HTMLTextExtractor with special characters."""
        extractor = HTMLTextExtractor()
        html = "Text with special chars: !@#$%^&*()_+-=[]{}|;:,.<>?"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Text with special chars: !@#$%^&*()_+-=[]{}|;:,.<>?"

    def test_html_text_extractor_with_unicode(self):
        """Test HTMLTextExtractor with unicode characters."""
        extractor = HTMLTextExtractor()
        html = "Text with unicode: 测试"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Text with unicode: 测试"

    def test_html_text_extractor_with_emoji(self):
        """Test HTMLTextExtractor with emoji."""
        extractor = HTMLTextExtractor()
        html = "Text with emoji: 🚨"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Text with emoji: 🚨"

    def test_html_text_extractor_with_quotes(self):
        """Test HTMLTextExtractor with quotes."""
        extractor = HTMLTextExtractor()
        html = 'Text with "double" and \'single\' quotes'

        extractor.feed(html)
        result = extractor.get_text()

        assert result == 'Text with "double" and \'single\' quotes'

    def test_html_text_extractor_with_very_long_text(self):
        """Test HTMLTextExtractor with very long text."""
        extractor = HTMLTextExtractor()
        long_text = 'a' * 10000
        html = f"<p>{long_text}</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == long_text + "\n"

    def test_html_text_extractor_with_very_deep_nesting(self):
        """Test HTMLTextExtractor with very deep nesting."""
        extractor = HTMLTextExtractor()
        html = "<div><div><div><div><div>Deep text</div></div></div></div></div>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after div tags
        assert result == "Deep text\n"

    def test_html_text_extractor_with_malformed_html(self):
        """Test HTMLTextExtractor with malformed HTML."""
        extractor = HTMLTextExtractor()
        html = "<p>Unclosed paragraph<div>Unclosed div"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p and div tags
        assert result == "Unclosed paragraph\nUnclosed div"

    def test_html_text_extractor_with_script_tags(self):
        """Test HTMLTextExtractor with script tags."""
        extractor = HTMLTextExtractor()
        html = "<p>Text before</p><script>alert('test');</script><p>Text after</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # Script tags are not handled specially, so their content is included
        assert result == "Text before\nalert('test');\nText after\n"

    def test_html_text_extractor_with_style_tags(self):
        """Test HTMLTextExtractor with style tags."""
        extractor = HTMLTextExtractor()
        html = "<p>Text before</p><style>body { color: red; }</style><p>Text after</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # Style tags are not handled specially, so their content is included
        assert result == "Text before\nbody { color: red; }\nText after\n"

    def test_html_text_extractor_with_comments(self):
        """Test HTMLTextExtractor with HTML comments."""
        extractor = HTMLTextExtractor()
        html = "<p>Text before</p><!-- This is a comment --><p>Text after</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # Comments are not handled specially, so they are included
        assert result == "Text before\nText after\n"

    def test_html_text_extractor_with_doctype(self):
        """Test HTMLTextExtractor with DOCTYPE declaration."""
        extractor = HTMLTextExtractor()
        html = "<!DOCTYPE html><html><body><p>Text content</p></body></html>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Text content\n"

    def test_html_text_extractor_with_meta_tags(self):
        """Test HTMLTextExtractor with meta tags."""
        extractor = HTMLTextExtractor()
        html = "<meta charset='utf-8'><p>Text content</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Text content\n"

    def test_html_text_extractor_with_link_tags(self):
        """Test HTMLTextExtractor with link tags."""
        extractor = HTMLTextExtractor()
        html = "<link rel='stylesheet' href='style.css'><p>Text content</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Text content\n"

    def test_html_text_extractor_with_img_tags(self):
        """Test HTMLTextExtractor with img tags."""
        extractor = HTMLTextExtractor()
        html = "<p>Text before</p><img src='image.jpg' alt='Image'><p>Text after</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Text before\nText after\n"

    def test_html_text_extractor_with_a_tags(self):
        """Test HTMLTextExtractor with anchor tags."""
        extractor = HTMLTextExtractor()
        html = "<p>Text before</p><a href='https://example.com'>Link text</a><p>Text after</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Text before\nLink text\nText after\n"

    def test_html_text_extractor_with_strong_tags(self):
        """Test HTMLTextExtractor with strong tags."""
        extractor = HTMLTextExtractor()
        html = "<p>Text before</p><strong>Bold text</strong><p>Text after</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Text before\nBold text\nText after\n"

    def test_html_text_extractor_with_em_tags(self):
        """Test HTMLTextExtractor with em tags."""
        extractor = HTMLTextExtractor()
        html = "<p>Text before</p><em>Italic text</em><p>Text after</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Text before\nItalic text\nText after\n"

    def test_html_text_extractor_with_span_tags(self):
        """Test HTMLTextExtractor with span tags."""
        extractor = HTMLTextExtractor()
        html = "<p>Text before</p><span>Span text</span><p>Text after</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags
        assert result == "Text before\nSpan text\nText after\n"

    def test_html_text_extractor_with_div_tags(self):
        """Test HTMLTextExtractor with div tags."""
        extractor = HTMLTextExtractor()
        html = "<p>Text before</p><div>Div text</div><p>Text after</p>"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p and div tags
        assert result == "Text before\nDiv text\nText after\n"

    def test_html_text_extractor_with_ul_li_tags(self):
        """Test HTMLTextExtractor with ul and li tags."""
        extractor = HTMLTextExtractor()
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Item 1Item 2"

    def test_html_text_extractor_with_ol_li_tags(self):
        """Test HTMLTextExtractor with ol and li tags."""
        extractor = HTMLTextExtractor()
        html = "<ol><li>Item 1</li><li>Item 2</li></ol>"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Item 1Item 2"

    def test_html_text_extractor_with_table_tags(self):
        """Test HTMLTextExtractor with table tags."""
        extractor = HTMLTextExtractor()
        html = "<table><tr><td>Cell 1</td><td>Cell 2</td></tr></table>"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Cell 1Cell 2"

    def test_html_text_extractor_with_form_tags(self):
        """Test HTMLTextExtractor with form tags."""
        extractor = HTMLTextExtractor()
        html = "<form><input type='text' value='Input text'><button>Button text</button></form>"

        extractor.feed(html)
        result = extractor.get_text()

        # Input tags with value attribute are not handled specially
        assert result == "Button text"

    def test_html_text_extractor_with_multiple_calls(self):
        """Test HTMLTextExtractor with multiple calls."""
        extractor = HTMLTextExtractor()

        # First call
        extractor.feed("<p>First text</p>")
        result1 = extractor.get_text()
        assert result1 == "First text\n"

        # Second call - the extractor accumulates text
        extractor.feed("<p>Second text</p>")
        result2 = extractor.get_text()
        assert result2 == "First text\nSecond text\n"

    def test_html_text_extractor_with_empty_html(self):
        """Test HTMLTextExtractor with empty HTML."""
        extractor = HTMLTextExtractor()
        html = ""

        extractor.feed(html)
        result = extractor.get_text()

        assert result == ""

    def test_html_text_extractor_with_only_tags(self):
        """Test HTMLTextExtractor with only HTML tags."""
        extractor = HTMLTextExtractor()
        html = "<p></p><div></div><span></span>"

        extractor.feed(html)
        result = extractor.get_text()

        # Empty tags result in empty string
        assert result == ""

    def test_html_text_extractor_with_only_text(self):
        """Test HTMLTextExtractor with only text."""
        extractor = HTMLTextExtractor()
        html = "Just plain text"

        extractor.feed(html)
        result = extractor.get_text()

        assert result == "Just plain text"

    def test_html_text_extractor_with_mixed_content(self):
        """Test HTMLTextExtractor with mixed content."""
        extractor = HTMLTextExtractor()
        html = "Text before<p>Paragraph text</p>Text after<br>Line break"

        extractor.feed(html)
        result = extractor.get_text()

        # The actual implementation adds newlines after p tags and br tags
        assert result == "Text before\nParagraph text\nText after\nLine break"
