"""
Keyboard-layout-aware SearchFilter.

When a user types with the wrong keyboard layout (e.g. Ukrainian instead of
English), the search query contains wrong characters. This filter tries
the original query plus layout-converted variants.
"""

from functools import reduce
from operator import or_

from django.db.models import Q
from rest_framework.filters import SearchFilter

EN_CHARS = "qwertyuiop[]asdfghjkl;'zxcvbnm,.`QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>~"
UA_CHARS = "йцукенгшщзхїфівапролджєячсмитьбю'ЙЦУКЕНГШЩЗХЇФІВАПРОЛДЖЄЯЧСМИТЬБЮ₴"

_en_to_ua = str.maketrans(EN_CHARS, UA_CHARS)
_ua_to_en = str.maketrans(UA_CHARS, EN_CHARS)


def _layout_variants(text: str) -> list[str]:
    """Return unique search variants: original + both layout conversions."""
    variants = {text}
    variants.add(text.translate(_en_to_ua))
    variants.add(text.translate(_ua_to_en))
    return list(variants)


class LayoutAwareSearchFilter(SearchFilter):
    """Drop-in replacement for DRF SearchFilter that also searches
    layout-converted variants of the query."""

    def filter_queryset(self, request, queryset, view):
        search_terms = self.get_search_terms(request)
        if not search_terms:
            return queryset

        search_fields = self.get_search_fields(view, request)
        if not search_fields:
            return queryset

        orm_lookups = [self.construct_search(str(field)) for field in search_fields]

        conditions = []
        for term in search_terms:
            for variant in _layout_variants(term):
                queries = [Q(**{lookup: variant}) for lookup in orm_lookups]
                conditions.append(reduce(or_, queries))

        queryset = queryset.filter(reduce(or_, conditions))
        return queryset
