from django.contrib import admin
from .models import URL, URLRedirect


class RedirectInline(admin.StackedInline):
    model = URLRedirect
    extra = 0
    max_num = 1


class URLAdmin(admin.ModelAdmin):
    list_display = ['path', 'modified']
    list_display_links = ['path']
    actions = None
    search_fields = ['^path']
    ordering = ('-modified',)
    inlines = [RedirectInline]
admin.site.register(URL, URLAdmin)
