from rest_framework import serializers
from .models import Holiday


class HolidaySerializer(serializers.ModelSerializer):
    # Read-only convenience fields surfaced from the FK
    financial_year_long  = serializers.CharField(
        source='financial_year.long_fy',
        read_only=True,
    )
    financial_year_short = serializers.CharField(
        source='financial_year.short_fy',
        read_only=True,
    )

    class Meta:
        model  = Holiday
        fields = [
            'id',
            'financial_year',        # PK — writable
            'financial_year_long',   # e.g. FY2025-2026 — read-only
            'financial_year_short',  # e.g. FY25-26     — read-only
            'holiday_date',
            'note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        fy           = attrs.get('financial_year') or (
            self.instance.financial_year if self.instance else None
        )
        holiday_date = attrs.get('holiday_date') or (
            self.instance.holiday_date if self.instance else None
        )

        if fy and holiday_date:
            if not (fy.start_date <= holiday_date <= fy.end_date):
                raise serializers.ValidationError({
                    'holiday_date': (
                        f'Date must fall within {fy.long_fy} '
                        f'({fy.start_date:%d %b %Y} – {fy.end_date:%d %b %Y}).'
                    )
                })

        return attrs