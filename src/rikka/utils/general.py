import re
import html

def clean_html(raw: str | None) -> str:
    """Clean HTML tags from a string."""
    if not raw:
        return "Not available :("

    text = re.sub(r'<.*?>', '', raw).strip()
    return html.unescape(text)

def get_referrer_for_url(url: str) -> str:
    """ Get an appropriate referrer for a given URL."""
    if "fast4speed" in url:
        return "https://allanime.day"

    elif "sunshinerays" in url:
        return "https://allmanga.to"

    else:
        return "https://allanime.day"