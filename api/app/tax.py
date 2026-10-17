"""Putting quotes on one GST basis before comparing them. Kept out of engine.py: the landed-cost formula and gates
are untouched; this only decides which pack price the engine is handed.

If GST is claimable as input tax credit, compare ex-GST; if not, compare GST-inclusive. A quote that does not say
whether its price includes GST (or at what rate) is treated as exclusive and flagged as an assumption to confirm.
We never invent a tax rate. Freight is taken as quoted.
"""
from typing import Literal, Optional, Tuple

TaxBasis = Literal["stated", "assumed_exclusive"]


def normalise_price(pack_price: float, tax_rate: Optional[float], includes_tax: Optional[bool],
                    claimable: bool) -> Tuple[float, TaxBasis]:
    if tax_rate is not None and tax_rate < 0:
        raise ValueError("tax rate cannot be negative")
    if tax_rate is None or includes_tax is None:
        return pack_price, "assumed_exclusive"
    factor = 1 + tax_rate / 100
    ex_tax = pack_price / factor if includes_tax else pack_price
    price = ex_tax if claimable else ex_tax * factor
    return round(price, 6), "stated"
