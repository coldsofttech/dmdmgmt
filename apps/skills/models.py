from django.db import models


class Skill(models.Model):
    skill = models.CharField(
        max_length=20,
        unique=True,
        help_text='Uppercase code, max 20 characters. E.g. AWSENGINEER',
    )
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['skill']

    def __str__(self):
        return self.skill
