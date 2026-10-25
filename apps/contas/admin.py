from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilizador


@admin.register(Utilizador)
class UtilizadorAdmin(UserAdmin):
    list_display = ("username", "email", "tipo", "is_active", "is_staff")
    list_filter = ("tipo", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (("Perfil", {"fields": ("tipo",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Perfil", {"fields": ("email", "tipo")}),
    )
