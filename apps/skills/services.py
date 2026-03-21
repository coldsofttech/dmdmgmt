from django.core.exceptions import ValidationError
from .models import Skill


class SkillService:
    @staticmethod
    def list_skills(filters=None):
        qs = Skill.objects.all()
        if not filters:
            return qs
        if filters.get('search'):
            term = filters['search']
            qs = qs.filter(skill__icontains=term) | qs.filter(description__icontains=term)
        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])
        return qs

    @staticmethod
    def get_skill(skill_id: int):
        return Skill.objects.get(pk=skill_id)

    @staticmethod
    def create_skill(data: dict) -> Skill:
        skill_code = data['skill'].strip().upper()
        if Skill.objects.filter(skill=skill_code).exists():
            raise ValidationError(f"Skill '{skill_code}' already exists.")
        skill = Skill(
            skill       = skill_code,
            description = data.get('description', '').strip(),
            is_active   = data.get('is_active', True),
        )
        skill.full_clean()
        skill.save()
        return skill

    @staticmethod
    def update_skill(skill_id: int, data: dict) -> Skill:
        skill = Skill.objects.get(pk=skill_id)
        if 'skill' in data:
            new_code = data['skill'].strip().upper()
            if Skill.objects.filter(skill=new_code).exclude(pk=skill_id).exists():
                raise ValidationError(f"Skill '{new_code}' already exists.")
            skill.skill = new_code
        if 'description' in data:
            skill.description = data['description'].strip()
        if 'is_active' in data:
            skill.is_active = data['is_active']
        skill.full_clean()
        skill.save()
        return skill

    @staticmethod
    def delete_skill(skill_id: int) -> None:
        Skill.objects.get(pk=skill_id).delete()
