"""F-81: the unwritten summary splits sentences only at a "." followed by whitespace."""

from src.pipeline.generate import GenerationConfig, _structured_summary


def test_dots_inside_names_urls_and_numbers_stay_whole():
    text = ("A deliberation tool (https://consider.it). Charts use Chart.js and "
            "images live at s3.amazonaws.com/Kumo02.png. 26 strategies, 1.6M+ combinations.")
    summary = _structured_summary(text, GenerationConfig(max_summary_chars=400))
    for whole in ("consider.it", "Chart.js", "s3.amazonaws.com/Kumo02.png", "1.6M+"):
        assert whole in summary
    assert ". js" not in summary and ". png" not in summary


def test_first_three_sentences_are_kept():
    text = "One. Two. Three. Four."
    assert _structured_summary(text, GenerationConfig()) == "One. Two. Three."


def test_text_without_a_period_gets_one():
    assert _structured_summary("No period at all", GenerationConfig()) == "No period at all."
