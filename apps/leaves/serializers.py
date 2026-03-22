from rest_framework import serializers
from .models import Leave


class LeaveSerializer(serializers.ModelSerializer):
    team_member_name   = serializers.CharField(source='team_member.display_name', read_only=True)
    team_name          = serializers.CharField(source='team_member.team.name',     read_only=True)
    financial_year_long  = serializers.CharField(source='financial_year.long_fy',  read_only=True)
    financial_year_short = serializers.CharField(source='financial_year.short_fy', read_only=True)

    class Meta:
        model  = Leave
        fields = [
            'id',
            'team_member',          # PK — writable
            'team_member_name',     # read-only display
            'team_name',            # read-only display
            'financial_year',       # PK — writable
            'financial_year_long',  # read-only display
            'financial_year_short', # read-only display
            'start_date',
            'end_date',
            'days',                 # read-only, auto-calculated
            'note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['days', 'created_at', 'updated_at']

    def validate(self, attrs):
        start = attrs.get('start_date') or (self.instance.start_date if self.instance else None)
        end   = attrs.get('end_date')   or (self.instance.end_date   if self.instance else None)
        fy    = attrs.get('financial_year') or (self.instance.financial_year if self.instance else None)

        if start and end:
            if end < start:
                raise serializers.ValidationError(
                    {'end_date': 'End date cannot be before start date.'}
                )
            if fy and (start < fy.start_date or end > fy.end_date):
                raise serializers.ValidationError({
                    'start_date': (
                        f'Dates must fall within {fy.long_fy} '
                        f'({fy.start_date:%d %b %Y} – {fy.end_date:%d %b %Y}).'
                    )
                })
        return attrs