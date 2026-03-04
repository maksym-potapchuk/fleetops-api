import django_filters

from .constants import EventType
from .models import FleetVehicleRegulationHistory, FleetVehicleRegulationSchema


class FleetVehicleRegulationSchemaFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr="icontains")
    is_default = django_filters.BooleanFilter()
    min_km = django_filters.NumberFilter(
        field_name="items__every_km",
        lookup_expr="gte",
    )
    max_km = django_filters.NumberFilter(
        field_name="items__every_km",
        lookup_expr="lte",
    )

    class Meta:
        model = FleetVehicleRegulationSchema
        fields = ["title", "is_default", "min_km", "max_km"]


class RegulationHistoryFilter(django_filters.FilterSet):
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
    event_type = django_filters.ChoiceFilter(choices=EventType.choices)

    class Meta:
        model = FleetVehicleRegulationHistory
        fields = ["event_type"]
