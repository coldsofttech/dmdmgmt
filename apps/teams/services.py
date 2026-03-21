from .models import Team
from django.core.exceptions import ValidationError

class TeamService:
    @staticmethod
    def list_teams(filters=None):
        qs = Team.objects.all()
        if filters:
            if filters.get('is_active') is not None:
                qs = qs.filter(is_active=filters['is_active'])
        return qs

    @staticmethod
    def get_team(team_id):
        return Team.objects.get(pk=team_id)

    @staticmethod
    def create_team(data: dict) -> Team:
        if Team.objects.filter(name=data['name']).exists():
            raise ValidationError(f"Team '{data['name']}' already exists.")
        # team = Team(**data)
        team = Team(
            name = data['name'],
            is_active = data.get('is_active', True),
        )
        team.full_clean()
        team.save()
        return team

    @staticmethod
    def update_team(team_id, data: dict) -> Team:
        team = Team.objects.get(pk=team_id)
        # for field, value in data.items():
        #     setattr(team, field, value)
        team.name = data.get('name', team.name)
        team.is_active = data.get('is_active', team.is_active)
        team.full_clean()
        team.save()
        return team

    @staticmethod
    def delete_team(team_id) -> None:
        Team.objects.get(pk=team_id).delete()
