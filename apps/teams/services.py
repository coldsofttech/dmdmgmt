from .models import Team
from django.core.exceptions import ValidationError

class TeamService:
    @staticmethod
    def list_teams(filters=None):
        qs = Team.objects.all()
        if not filters:
            return qs
        if filters.get('search'):
            term = filters['search']
            qs = qs.filter(name__icontains=term) | qs.filter(description__icontains=term)
        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])
        # if filters:
        #     if filters.get('is_active') is not None:
        #         qs = qs.filter(is_active=filters['is_active'])
        return qs

    @staticmethod
    def get_team(team_id: int):
        return Team.objects.get(pk=team_id)

    @staticmethod
    def create_team(data: dict) -> Team:
        if Team.objects.filter(name=data['name']).exists():
            raise ValidationError(f"Team '{data['name']}' already exists.")
        # team = Team(**data)
        team = Team(
            name = data['name'],
            description = data.get('description', '').strip(),
            is_active = data.get('is_active', True),
        )
        team.full_clean()
        team.save()
        return team

    @staticmethod
    def update_team(team_id: int, data: dict) -> Team:
        team = Team.objects.get(pk=team_id)
        if 'name' in data:
            new_name = data['name']
            if Team.objects.filter(name=new_name).exclude(pk=team_id).exists():
                raise ValidationError(f"Team '{new_name}' already exists.")
            team.name = new_name
        if 'description' in data:
            team.description = data['description'].strip()
        if 'is_active' in data:
            team.is_active = data['is_active']
        # team.name = data.get('name', team.name)
        # team.is_active = data.get('is_active', team.is_active)
        team.full_clean()
        team.save()
        return team

    @staticmethod
    def delete_team(team_id: int) -> None:
        Team.objects.get(pk=team_id).delete()
