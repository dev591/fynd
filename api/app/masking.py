"""Hiding contact details in free text until a seller is revealed. Imperfect by design: it catches common
phone and email formats, not someone who spells a number out in words. The UI says so."""
import re

HIDDEN = "[hidden until unlocked]"

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
# Indian mobiles (with or without +91), written as 10 digits or split 5+5 / 3+3+4 with spaces or dashes.
_IN_MOBILE = re.compile(r"(?<![\d,.])(?:\+?91[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}(?![\d,])")
# Anything else that looks like a phone number: optional +country, then 9 to 14 digits with ordinary separators.
_GENERIC = re.compile(r"(?<![\d,.])(?:\+\d{1,3}[\s\-]?)?(?:\(?\d{2,5}\)?[\s\-]?){2,4}\d{2,5}(?![\d,])")


def _looks_like_phone(match: str) -> bool:
    digits = re.sub(r"\D", "", match)
    return 9 <= len(digits) <= 14 and not re.fullmatch(r"\d{1,3}(?:,\d{2,3})+", match.strip())


def scrub(text: str | None, placeholder: str = HIDDEN) -> str | None:
    """Replace emails and phone numbers. Prices, quantities and lead times are left alone."""
    if not text:
        return text
    out = _EMAIL.sub(placeholder, text)
    out = _IN_MOBILE.sub(placeholder, out)
    out = _GENERIC.sub(lambda m: placeholder if _looks_like_phone(m.group(0)) else m.group(0), out)
    return out
