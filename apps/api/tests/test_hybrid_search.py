from unittest.mock import patch

from app.services.retrieval import _apply_reranker, _hybrid_rerank, _keyword_overlap_score


class FakeChunk:
    def __init__(self, text: str):
        self.text = text


def test_keyword_overlap_score_counts_distinct_query_terms_found():
    assert _keyword_overlap_score("mobile otp", "the otp code is sent to the mobile app") == 1.0
    assert _keyword_overlap_score("mobile OTP verification", "the otp code is sent to the mobile app") == 2 / 3
    assert _keyword_overlap_score("mobile OTP verification", "nothing relevant here") == 0.0


def test_keyword_overlap_score_ignores_short_words_and_empty_query():
    assert _keyword_overlap_score("a to of", "anything") == 0.0
    assert _keyword_overlap_score("", "anything") == 0.0


def test_hybrid_rerank_promotes_exact_keyword_match_over_weaker_vector_score():
    # chunk A: lower vector score but contains every query term verbatim
    # chunk B: higher vector score but shares no query terms
    chunk_a = FakeChunk("def verify_otp(): check the mobile verification code")
    chunk_b = FakeChunk("class LoanApplication: unrelated business logic")
    rows = [(chunk_a, "otp.py", 0.55), (chunk_b, "loan.py", 0.60)]

    reranked = _hybrid_rerank(rows, "mobile otp verification")

    assert reranked[0][0] is chunk_a
    assert reranked[1][0] is chunk_b


def test_hybrid_rerank_is_a_noop_without_query_text():
    chunk_a = FakeChunk("anything")
    rows = [(chunk_a, "a.py", 0.9)]
    assert _hybrid_rerank(rows, "") == rows


@patch("app.services.retrieval.rerank_scores")
def test_apply_reranker_reorders_by_cross_encoder_score_but_keeps_displayed_score(mock_rerank):
    chunk_a = FakeChunk("a")
    chunk_b = FakeChunk("b")
    rows = [(chunk_a, "a.py", 0.9), (chunk_b, "b.py", 0.5)]
    # Cross-encoder disagrees with the hybrid order - b is actually more relevant.
    mock_rerank.return_value = [0.1, 0.9]

    reranked = _apply_reranker(rows, "query")

    assert [r[0] for r in reranked] == [chunk_b, chunk_a]
    assert reranked[0][2] == 0.5  # displayed score is still the original hybrid score, not the cross-encoder logit
    assert reranked[1][2] == 0.9


@patch("app.services.retrieval.rerank_scores")
def test_apply_reranker_falls_back_to_original_order_when_model_unavailable(mock_rerank):
    mock_rerank.return_value = None
    chunk_a = FakeChunk("a")
    rows = [(chunk_a, "a.py", 0.9)]

    assert _apply_reranker(rows, "query") == rows
