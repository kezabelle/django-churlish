from itertools import chain

from collections import namedtuple
try:
    from itertools import izip_longest as zip_longest
except ImportError:  # pragma: no-cover ... Python 3.
    from itertools import zip_longest

from django.contrib import admin
from .models import URL
from .admin_inlines import (VisibleInline, RedirectInline,
                            SimpleAccessInline, GroupAccessInline,
                            UserAccessInline)


RuntimeDiscovered = namedtuple('RuntimeDiscovered', 'inline model relation')
InlineRelation = namedtuple('InlineRelation', 'inline relation')


class URLAdmin(admin.ModelAdmin):
    list_display = ('site', 'path', 'modified')
    list_display_links = ('site', 'path', 'modified')
    date_hierarchy = 'modified'
    actions = None
    search_fields = ['^path']
    ordering = ('site', '-modified')
    inlines = (VisibleInline, RedirectInline, SimpleAccessInline,
               GroupAccessInline, UserAccessInline)

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

    def get_runtime_relations_and_inlines(self):
        relations = tuple(self.get_runtime_relations())
        zipped_together = zip_longest(self.inlines[:], relations,
                                      fillvalue=None)
        models_and_inlines = (
            RuntimeDiscovered(inline=inline, model=inline.model,
                              relation=relation)
            for inline, relation in zipped_together
            if inline is not None and relation is not None)
        return models_and_inlines

    def get_middleware_classes(self):
        for row in self.get_runtime_relations_and_inlines():
            if hasattr(row.inline, 'get_churlish_middlewares'):
                proper_inline = row.inline(row.model, self.admin_site)
                for mw in proper_inline.get_churlish_middlewares():
                    yield mw
            if hasattr(row.model, 'get_churlish_middlewares'):
                proper_model = row.model()
                for mw in proper_model.get_churlish_middlewares():
                    yield mw

    def get_middlewares(self):
        return tuple(x() for x in self.get_middleware_classes())

    def get_queryset(self, *args, **kwargs):
        relations = tuple(self.get_runtime_relations())
        qs = super(URLAdmin, self).get_queryset(*args, **kwargs)
        return qs.select_related(*relations)

    def get_list_display(self, *args, **kwargs):
        instantiated = (
            InlineRelation(inline=item.inline(item.model, self.admin_site),
                           relation=item.relation)
            for item in self.get_runtime_relations_and_inlines()
            if hasattr(item.inline, 'get_urladmin_display')
            and hasattr(item.inline, 'get_urladmin_display_func'))
        called = tuple(inrel.inline.get_urladmin_display_func(inrel.relation)
                       for inrel in instantiated)
        return self.__class__.list_display + called

    def get_list_filter(self, *args, **kwargs):
        instantiated = (
            InlineRelation(inline=item.inline(item.model, self.admin_site),
                           relation=item.relation)
            for item in self.get_runtime_relations_and_inlines()
            if hasattr(item.inline, 'get_urladmin_filter_cls'))
        called = tuple(inrel.inline.get_urladmin_filter_cls(*args, **kwargs)
                       for inrel in instantiated)
        self.list_filter = called
        return self.list_filter

    # def lookup_allowed(self, lookup, value):
    #     return True
admin.site.register(URL, URLAdmin)
