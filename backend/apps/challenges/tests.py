import pytest

from .verifiers import get_supported_languages, get_verifier
from .verifiers.base import VerificationResult


class TestRustVerifier:
    def setup_method(self):
        self.verifier = get_verifier("rust")

    def test_accepts_valid_rust_code(self):
        code = "fn add(a: i32, b: i32) -> i32 {\n    a + b\n}"
        result = self.verifier.verify(code)
        assert result.accepted is True
        assert result.score_delta == 10

    def test_rejects_empty_code(self):
        result = self.verifier.verify("")
        assert result.accepted is False
        assert "empty" in result.feedback.lower()

    def test_rejects_unbalanced_braces(self):
        code = 'fn main() { println!("hi");'
        result = self.verifier.verify(code)
        assert result.accepted is False
        assert "unclosed" in result.feedback.lower()

    def test_rejects_unmatched_closing_brace(self):
        code = "fn main() { } }"
        result = self.verifier.verify(code)
        assert result.accepted is False
        assert "unexpected" in result.feedback.lower()

    def test_rejects_mismatched_delimiters(self):
        code = "fn main(] { }"
        result = self.verifier.verify(code)
        assert result.accepted is False
        assert "mismatched" in result.feedback.lower()

    def test_exact_match_succeeds(self):
        expected = "fn add(a: i32, b: i32) -> i32 {\n    a + b\n}"
        code = "fn add(a: i32, b: i32) -> i32 {\n    a + b\n}"
        result = self.verifier.verify(code, expected=expected)
        assert result.accepted is True
        assert result.score_delta == 10

    def test_structural_match_partial_credit(self):
        expected = "fn add(a: i32, b: i32) -> i32 {\n    a + b\n}"
        code = "fn add(x: i32, y: i32) -> i32 {\n    x + y\n}"
        result = self.verifier.verify(code, expected=expected)
        assert result.accepted is False
        assert result.score_delta == 5

    def test_wrong_code_no_match(self):
        expected = "fn add(a: i32, b: i32) -> i32 {\n    a + b\n}"
        code = "fn subtract(a: i32, b: i32) -> i32 {\n    a - b\n}"
        result = self.verifier.verify(code, expected=expected)
        assert result.accepted is False
        assert result.score_delta == 0

    def test_rejects_short_code(self):
        code = "fn"
        result = self.verifier.verify(code)
        assert result.accepted is False
        assert "too short" in result.feedback.lower()

    def test_get_verifier_returns_none_for_unknown(self):
        assert get_verifier("brainfuck") is None

    def test_supported_languages_includes_rust(self):
        langs = get_supported_languages()
        assert "rust" in langs

    def test_get_verifier_returns_callable(self):
        verifier = get_verifier("rust")
        assert callable(verifier.verify)

    def test_no_expected_code_passes_syntax_check(self):
        code = 'fn main() {\n    println!("Hello, world!");\n}'
        result = self.verifier.verify(code)
        assert result.accepted is True

    def test_string_format_braces_dont_confuse_checker(self):
        code = 'fn main() {\n    println!("Count: {}", n);\n}'
        result = self.verifier.verify(code)
        assert result.accepted is True

    def test_block_comments_skipped(self):
        code = "fn main() {\n    /* { */\n    let x = 1;\n}"
        result = self.verifier.verify(code)
        assert result.accepted is True

    def test_line_comments_skipped(self):
        code = "fn main() {\n    // { }\n    let x = 1;\n}"
        result = self.verifier.verify(code)
        assert result.accepted is True

    def test_escaped_quotes_in_strings(self):
        code = 'fn main() {\n    println!("hello \\"world\\"");\n}'
        result = self.verifier.verify(code)
        assert result.accepted is True

    def test_python_verifier_accepts_valid_code(self):
        verifier = get_verifier("python")
        code = "def add(a, b):\n    return a + b"
        result = verifier.verify(code)
        assert result.accepted is True

    def test_python_verifier_rejects_empty(self):
        verifier = get_verifier("python")
        result = verifier.verify("")
        assert result.accepted is False

    def test_python_verifier_rejects_unbalanced(self):
        verifier = get_verifier("python")
        code = 'def foo():\n    print("hi"'
        result = verifier.verify(code)
        assert result.accepted is False

    def test_python_verifier_handles_strings_with_braces(self):
        verifier = get_verifier("python")
        code = 's = "hello {world} (test)"'
        result = verifier.verify(code)
        assert result.accepted is True

    def test_python_verifier_handles_comments(self):
        verifier = get_verifier("python")
        code = "# this has { and }\nx = 1"
        result = verifier.verify(code)
        assert result.accepted is True

    def test_python_verifier_supported(self):
        langs = get_supported_languages()
        assert "python" in langs

    def test_realistic_rust_exercise_code(self):
        code = """let numbers = vec![5, 10, 15, 20, 25, 30];
let mut sum = 0;
let mut processed_count = 0;

for num in numbers {
    if num % 2 == 0 {
        println!("Found an even number: {}", num);
        sum += num;
        processed_count += 1;
    } else {
        println!("Skipping odd number: {}", num);
    }
}

println!("----------------------------");
println!("Total even numbers added: {}", processed_count);
println!("The final sum is: {}", sum);"""
        result = self.verifier.verify(code)
        assert result.accepted is True
