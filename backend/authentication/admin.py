from django.contrib import admin

from authentication.models import AdminProfile


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'last_login_ip', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')
