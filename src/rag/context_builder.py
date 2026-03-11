"""
Context builder module for formatting retrieved chunks into LLM prompt context.
"""

from typing import List, Dict
from markdown import Markdown
from io import StringIO


# ============= Markdown stripping =============
# Markdown stripping functions taken from: https://fnordig.de/til/Python/strip-markdown-syntax.html


def unmark_element(element, stream=None):
    if stream is None:
        stream = StringIO()
    if element.text:
        stream.write(element.text)
    for sub in element:
        unmark_element(sub, stream)
    if element.tail:
        stream.write(element.tail)

    return stream.getvalue()

Markdown.output_formats["plain"] = unmark_element
__md = Markdown(output_format="plain")
__md.stripTopLevelTags = False

def strip_markdown(text):
    return __md.convert(text)

# ==========================


class ContextBuilder:
    """
    Formats retrieved chunks into context for LLM prompts.
    """
    
    def build_context(self, chunks: List[str], metadata: List[Dict] = None) -> str:
        """
        Build a formatted context string from retrieved chunks.
        
        Takes a list of chunk text strings, strips their markdown formatting, and
        combines them into a single formatted string suitable for inclusion in an LLM prompt.
        
        The metadata parameter is accepted but not used in formatting — it is kept here
        so that future extensions can incorporate source attribution, scores, or other
        chunk-level information without changing the method signature.
        
        Example output:
        Content of chunk 1...
        ---
        Content of chunk 2...
        """
        if not chunks:
            return ""
        
        # Strip markdown from each chunk
        stripped_parts = [strip_markdown(chunk) for chunk in chunks]
        
        # Join with separator
        context = "\n\n---\n\n".join(stripped_parts)
        
        return context


