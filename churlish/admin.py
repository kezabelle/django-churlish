from django.contrib import admin
from .models import URL


class URLAdmin(admin.ModelAdmin):
    list_display = ['path', 'modified']
    list_display_links = ['path']
    actions = None
    search_fields = ['^path']
    ordering = ('-modified',)
admin.site.register(URL, URLAdmin)
