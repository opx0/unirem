import re

from core.models import Notice
from intake.models import ExtractionRun

# Common question words do not identify the source the student is looking for.
STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
    ]
)
WORD = re.compile(r"[^\W_]+", re.UNICODE)
PASSAGE = re.compile(r"[^\n.!?]+(?:[.!?]+|$|\n)")


def answer_question(owner, question):
    """Return verbatim matching passages, without inferring an answer."""
    terms = set(WORD.findall(question.casefold())) - STOP_WORDS
    if not terms:
        return [], False

    sources = []
    notices = Notice.objects.filter(owner=owner).order_by("pk")
    for notice in notices:
        sources.extend(
            (notice, label, text, False)
            for label, text in (
                ("Notice title", notice.title),
                ("Notice text", notice.original_text),
            )
            if text
        )
    runs = (
        ExtractionRun.objects.filter(
            owner=owner, notice__owner=owner, status=ExtractionRun.Status.SUCCESS
        )
        .select_related("notice")
        .order_by("pk")
    )
    for run in runs:
        for label, text in (
            ("Reviewed extraction", run.reviewed_text),
            ("Original extraction", run.extracted_text),
        ):
            if text and not (
                label == "Original extraction" and text == run.reviewed_text
            ):
                sources.append((run.notice, label, text, True))

    results = []
    seen = set()
    for notice, label, text, extraction in sources:
        for match in PASSAGE.finditer(text):
            snippet = match.group().strip()
            if not terms.issubset(set(WORD.findall(snippet.casefold()))):
                continue
            key = (notice.pk, snippet)
            if key in seen:
                continue
            seen.add(key)
            if len(results) == 20:
                return results, True
            results.append(
                {
                    "notice": notice,
                    "label": label,
                    "snippet": snippet,
                    "extraction": extraction,
                }
            )
    return results, False
