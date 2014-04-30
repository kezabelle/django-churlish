from itertools import chain
from django.contrib import admin
from .models import URL, URLRedirect, URLVisible


class RedirectInline(admin.StackedInline):
    model = URLRedirect
    extra = 0
    max_num = 1

    def get_urladmin_display(self, obj):
        return ''

class VisibleInline(admin.StackedInline):
    model = URLVisible
    extra = 0
    max_num = 1

    def get_urladmin_display(self, obj):
        return ''


class URLAdmin(admin.ModelAdmin):
    list_display = ['path']
    list_display_links = ['path']
    actions = None
    search_fields = ['^path']
    ordering = ('-modified',)
    inlines = [VisibleInline, RedirectInline]

    def get_runtime_relations(self):
        """
        For the middleware, of all things.
        Because this is the best place to find out wtf we might want to
        ask for at runtime without configuration.
        """
        models = (x.model for x in self.inlines[:] if hasattr(x, 'model'))
        fields = (x._meta.get_fields_with_model() for x in models)
        flat_fields = chain(*fields)
        just_fields = (x[0] for x in flat_fields)
        only_rels = (x for x in just_fields
                     if hasattr(x, 'rel'))
        only_good_rels = (x for x in only_rels if x.rel is not None)
        only_ours = (x for x in only_good_rels if x.rel.to == URL)
        accessors = (x.related.get_accessor_name() for x in only_ours
                     if hasattr(x, 'related'))
        return accessors

    def get_queryset(self, *args, **kwargs):
        relations = tuple(self.get_runtime_relations())
        qs = super(URLAdmin, self).get_queryset(*args, **kwargs)
        return qs.select_related(*relations)

    def get_list_display(self, *args, **kwargs):
        relations = tuple(self.get_runtime_relations())
        return ('path', 'modified') + relations
admin.site.register(URL, URLAdmin)
