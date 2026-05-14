from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Team, TeamSeat


class TeamSeatInline(admin.TabularInline):
    model  = TeamSeat
    extra  = 1


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'created_at')
    inlines      = [TeamSeatInline]


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'created_at')
    fieldsets    = UserAdmin.fieldsets + (
        ('Meta', {'fields': ('created_at',)}),
    )
    readonly_fields = ('created_at',)


@admin.register(TeamSeat)
class TeamSeatAdmin(admin.ModelAdmin):
    list_display = ('user', 'team', 'role', 'joined_at')
    list_filter  = ('role',)