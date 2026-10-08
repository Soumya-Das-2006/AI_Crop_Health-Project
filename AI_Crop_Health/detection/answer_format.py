"""
Answer formatting
=================
Ask AI answers are authored in markdown and rendered to HTML here, server-side.

WHY SERVER-SIDE
---------------
Two reasons. First, it is testable: a rendering bug shows up in the suite
rather than in a farmer's browser. Second, model output is untrusted text -
it must be sanitised before it goes anywhere near a page, and doing that in
JavaScript means shipping a sanitiser and trusting it.

The allowed tag set is deliberately small. An answer about a diseased leaf
needs headings, emphasis, lists and paragraphs. It never needs images,
iframes, scripts, styles or links, so none of those survive sanitising - a
model that emits them (or is talked into it by a crafted question) produces
inert text instead of markup.
"""

import re

import bleach
import markdown as markdown_lib

# Everything an agronomic answer legitimately uses, and nothing else.
ALLOWED_TAGS = [
    "h3", "h4", "h5",
    "p", "br", "hr",
    "strong", "b", "em", "i",
    "ul", "ol", "li",
    "blockquote",
    "code", "pre",
    "table", "thead", "tbody", "tr", "th", "td",
]

# No attributes at all: no href, no src, no style, no class, no event handlers.
ALLOWED_ATTRIBUTES = {}

# h1/h2 would fight the page's own heading hierarchy, so they are demoted
# rather than dropped - the text stays, it just sits at the right level.
_HEADING_DEMOTIONS = [
    ("<h1>", "<h3>"), ("</h1>", "</h3>"),
    ("<h2>", "<h3>"), ("</h2>", "</h3>"),
    ("<h6>", "<h5>"), ("</h6>", "</h5>"),
]


# bleach removes these tags but keeps the text inside them, which would put
# raw script source on the page as visible prose. Drop the whole block first.
_SCRIPTISH_BLOCK = re.compile(
    r"<\s*(script|style|iframe|object|embed)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)


def render_markdown(text):
    """
    Markdown -> sanitised HTML fragment.

    Returns an empty string for empty input. Never raises on malformed
    markdown: the worst case is that some syntax renders literally, which is
    far better than a 500 on the answer the farmer is waiting for.
    """
    if not text or not text.strip():
        return ""

    text = _SCRIPTISH_BLOCK.sub("", text)

    try:
        html = markdown_lib.markdown(
            text,
            extensions=["extra", "sane_lists", "nl2br"],
            output_format="html",
        )
    except Exception:
        # Fall back to the raw text as a paragraph rather than losing the answer.
        html = "<p>{0}</p>".format(bleach.clean(text, tags=[], strip=True))

    for old, new in _HEADING_DEMOTIONS:
        html = html.replace(old, new)

    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    ).strip()
