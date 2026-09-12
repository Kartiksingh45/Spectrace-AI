from app.services.chunking import chunk_js_ts_code, chunk_python_code

PYTHON_SOURCE = '''\
def verify_otp(code: str) -> bool:
    """Check the OTP code against the stored value."""
    return code == "123456"


class LoanApplication:
    def submit(self):
        return True
'''


def test_chunk_python_code_splits_by_function_and_class():
    candidates = chunk_python_code(PYTHON_SOURCE, "app/loans.py")
    assert len(candidates) == 2

    names = {c.metadata["symbol_name"] for c in candidates}
    assert names == {"verify_otp", "LoanApplication"}
    for c in candidates:
        assert c.metadata["chunk_strategy"] == "ast"
        assert c.metadata["file_path"] == "app/loans.py"
        assert c.metadata["start_line"] is not None
        assert c.metadata["end_line"] >= c.metadata["start_line"]


def test_chunk_python_code_falls_back_on_syntax_error():
    broken_source = "def verify_otp(:\n    return True"
    candidates = chunk_python_code(broken_source, "app/broken.py")
    assert len(candidates) > 0
    assert all(c.metadata["chunk_strategy"] == "fallback" for c in candidates)
    assert all(c.metadata["symbol_name"] is None for c in candidates)


JS_SOURCE = """
function verifyOtp(code) {
  return code === '123456';
}

export class LoanApplication {
  submit() {
    return true;
  }
}

const requiresOtp = (amount) => amount > 1000;
"""


def test_chunk_js_ts_code_splits_by_top_level_declarations():
    candidates = chunk_js_ts_code(JS_SOURCE, "app/loans.ts")
    assert len(candidates) == 3
    names = {c.metadata["symbol_name"] for c in candidates}
    assert names == {"verifyOtp", "LoanApplication", "requiresOtp"}
    assert all(c.metadata["language"] == "typescript" for c in candidates)
    assert all(c.metadata["chunk_strategy"] == "heuristic" for c in candidates)


def test_chunk_js_ts_code_falls_back_when_no_declarations_found():
    candidates = chunk_js_ts_code("const x = 1;\nconsole.log(x);\n" * 50, "app/notes.js")
    assert len(candidates) > 0
    assert all(c.metadata["chunk_strategy"] == "fallback" for c in candidates)
