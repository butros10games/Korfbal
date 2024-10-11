from django.contrib import admin

from .models import Club

class club_admin(admin.ModelAdmin):
    list_display = ["id_uuid", "name"]
    show_full_result_count = False
    
    class Meta:
        model = Club
admin.site.register(Club, club_admin)