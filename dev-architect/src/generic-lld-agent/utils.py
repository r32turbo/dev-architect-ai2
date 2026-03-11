def clean_text(text: str) -> str:
    """Clean and normalize text."""
    return text.strip()

def format_markdown(title: str, content: str) -> str:
    """Format content as a markdown section."""
    return f"## {title}\n\n{content}\n"