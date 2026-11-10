"""F-87 (survey 2026-11-02 / 11-09): records whose abstract field only re-states the title
("AUTHORS; Title, Journal…", the tail of the title, the title in capitals) are marked at the
source and named in one line. The text is kept, so grounding and echo do not change."""

from __future__ import annotations

from src.core.models import Work
from src.pipeline.delegate import (
    TITLE_ONLY_ABSTRACT_KEY,
    material_from_work,
    title_only_abstract,
    title_only_line,
)


def test_shapes_seen_in_the_survey_are_named():
    # 2026-11-09 W2138534101 / W2906297801, 2026-11-02 W2343400145 (live text, 2026-11-10)
    assert title_only_abstract(
        "Leverage-Saliency Theory of Survey Participation",
        "ROBERT M. GROVES, ELEANOR SINGER, AMY CORNING; Leverage-Saliency Theory of Survey "
        "Participation: Description and an Illustration*, Public Opinion Quarterly") == "title_echo"
    assert title_only_abstract(
        "La monitorización de la estimación de voto con modelos ponderados y no ponderados: un test empírico",
        "test empírico") == "title_fragment"
    assert title_only_abstract(
        "Graficzne metody odwzorowania i klasyfikacji chemizmu wód podziemnych",
        "REPRESENTATION, AND CLASSIFICATION OF GROUNDWATER CHEMISTRY BY GRAPHIC METHODS BASED ON "
        "THE FERET TRIANGLE AND TRIANGULAR-RHOMB PATTERNS \r\n\r\n.") == "caps_heading"


def test_real_abstracts_that_paraphrase_the_title_are_not_named():
    # 2026-11-10 scan: the word-share rule named this cut abstract; the contiguous rule does not
    assert title_only_abstract(
        "Why Shorter Advertisement Breaks Reduce Radio Advertisement Avoidance",
        "Low-clutter radio stations have shorter advertisement breaks to attract listeners, increase "
        "advertisement effectiveness, and potentially reduce radio advertisement avoidance.") is None
    assert title_only_abstract("Sampling bias", "Sampling bias means that the samples of a stochastic "
                               "variable that are collected to determine its distribution are selected "
                               "incorrectly.") is None
    assert title_only_abstract("A title", "") is None


def test_material_carries_the_mark_and_the_line_names_it():
    echo = Work(id="https://openalex.org/W1", title="Evaluating Interval Forecasts",
                abstract="Peter F. Christoffersen, Evaluating Interval Forecasts, International "
                         "Economic Review, Vol. 39, No. 4", year=1998,
                venue="IER", doi=None, cited_by_count=1)
    real = Work(id="https://openalex.org/W2", title="Evaluating Interval Forecasts",
                abstract="We propose a test of conditional coverage for interval forecasts.", year=1998,
                venue="IER", doi=None, cited_by_count=1)
    m1, m2 = material_from_work(echo), material_from_work(real)
    assert m1[TITLE_ONLY_ABSTRACT_KEY] == "title_echo"
    assert m1["abstract"].startswith("Peter F.")  # text kept
    assert TITLE_ONLY_ABSTRACT_KEY not in m2
    line = title_only_line([m1, m2])
    assert line and "W1" in line and "W2" not in line and "F-87" in line
    assert title_only_line([m2]) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
