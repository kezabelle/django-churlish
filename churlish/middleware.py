import re
import logging
from collections import namedtuple
from django.conf import settings
from django.utils.functional import cached_property
from django.http import (Http404, HttpResponseRedirect,
                         HttpResponsePermanentRedirect)
from django.core.urlresolvers import reverse_lazy, NoReverseMatch
from .models import URL, URLVisible, URLRedirect

try:
    from django.utils.timezone import now
except ImportError:
    from datetime import datetime
    now = datetime.now


logger = logging.getLogger(__name__)


URLData = namedtuple('URLData', 'perfect imperfect all path')


class RequestURL(object):
    def get_prefetch_related(self):
        return ()

    def get_select_related(self):
        return ()

    def get_query_set(self, request, instance):
        prefetches = self.get_prefetch_related()
        selects = self.get_select_related()
        qs = instance.get_ancestors(include_self=True)
        if selects:
            qs = qs.select_related(*selects)
        if prefetches:
            qs = qs.prefetch_related(*prefetches)
        return qs

    def get_url_data(self, request):
        url = URL(path=request.path)
        all_urls = tuple(
            self.get_query_set(request=request, instance=url).iterator())

        imperfect = None
        perfect = None
        if all_urls:
            imperfect = tuple(x for x in all_urls if x.is_ancestor_of(url))
            perfect = tuple(x for x in all_urls if x.is_same_as(url))

        outdata = URLData(perfect=perfect, imperfect=imperfect,
                          all=all_urls, path=request.path)
        return outdata

    def get_exclusions(self):
        try:
            admin_root = reverse_lazy('admin:index')
        except NoReverseMatch:
            admin_root = None

        might_need_excluding = (
            getattr(settings, 'STATIC_URL', None),
            getattr(settings, 'MEDIA_URL', None),
            '/favicon.ico$',
            admin_root,
            '/__debug__/',
            '/debug_toolbar/',
        )
        for exclude in might_need_excluding:
            if exclude:
                yield r'^{exclude!s}'.format(exclude=exclude)
        for configured_exclude in getattr(settings, 'CHURLISH_EXCLUDES', ()):
            if configured_exclude:
                yield configured_exclude

    @cached_property
    def compiled_exclusions(self):
        return tuple(re.compile(x, re.VERBOSE) for x in self.get_exclusions())

    def request_is_excluded(self, request):
        for exclusion in self.compiled_exclusions:
            if exclusion.search(request.path):
                return True
        return False

class ChurlishMiddleware(object):
    __slots__ = ('handler',)
    def __init__(self):
        self.handler = RequestURL()
    
    def process_request(self, request):
        if self.handler.request_is_excluded(request=request):
            return None  # no match, so continue with other middlewares
        request.churlish = self.handler.get_url_data(request=request)
        if len(request.churlish.all) < 1:
            return None   # no match, so continue with other middlewares
        from django.contrib import admin
        try:
            urladmin = admin.site._registry[URL]
        except KeyError:
            # Not mounted into the admin, so we can't figure out which
            # relations might affect the URL instances.
            return None

        bound_mws = urladmin.get_middlewares()
        bound_urls = request.churlish.all
        bitset = []
        for url in bound_urls:
            for mw in bound_mws:
                ok = mw.has_object_permission(request=request, obj=url, view=None)
                if not ok and hasattr(mw, 'error'):
                    bitset.append(ok)
                    mw.error(request=request, obj=url)
                elif ok and hasattr(mw, 'response'):
                    return mw.response(request=request, obj=url)
        
        # we should only hit this condition if a test failed, but didn't try
        # to handle it's business by implemementing .error()
        if not all(bitset):
            raise Http404("Request failed tests for this URL")

