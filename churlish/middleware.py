import re
import logging
from collections import namedtuple
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


ChurlishData = namedtuple('ChurlishData', 'perfecti imperfect all path')


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
        return qs.iterator()

    def get_or_set_url(self, request):
        request_attr = getattr(request, 'churlish', None)
        if request_attr is not None:
            return request_attr
        url = URL(path=request.path)
        all_urls = tuple(self.get_query_set(request=request, instance=url))

        imperfect = None
        if all_urls:
            imperfect = tuple(x for x in all_urls if x.is_ancestor_of(url))

        try:
            perfect = tuple(x for x in all_urls if x.is_same_as(url))
        except StopIteration:
            perfect = None

        outdata = ChurlishData(perfect=perfect, imperfect=imperfect,
                               all=all_urls, path=request.path)
        request.churlish = outdata
        return outdata

    def get_exclusions(self):
        try:
            admin_root = reverse_lazy('admin:index')
        except NoReverseMatch:
            admin_root = None
        static_root = getattr(settings, 'STATIC_URL', None)
        media_root = getattr(settings, 'MEDIA_URL', None)
        for exclude in (admin_root, static_root, media_root):
            if exclude:
                yield r'^{exclude!s}'.format(exclude=exclude)
        for configured_exclude in getattr(settings, 'CHURLISH_EXCLUDES', ()):
            if configured_exclude:
                yield configured_exclude

    @cached_property
    def compiled_exclusions(self):
        return tuple(re.compile(x, re.VERBOSE) for x in self.get_exclusions())

    def is_excluded(self, request):
        for exclusion in self.compiled_exclusions:
            if exclusion.search(request.path):
                return True
        return False


class IsVisible(RequestURL):
    """
    Allows for '/a/b/c/' to be hidden only when it is explicitly marked
    as unpublished
    """
    def get_object(self, request):
        raise NotImplementedError

    def process_request(self, request):
        if self.is_excluded():
            return None
        url = self.get_object()
        if url is None:
            return None  # no match, so continue with other middlewares
        return self.handle_unpublished(url=url, request=request)

    def handle_unpublished(self, url, request):
        if not url.is_pubished:
            msg = ("URL (pk: {url}) has publishing information (pk: {vis}) "
                   "which prevents it from being displayed now "
                   "({now})".format(url=url.url_id, vis=url.pk, now=now()))
            logger.error(msg, extra={'request': request, 'status_code': 404})
            raise Http404("URL is marked as unpublished explicitly")
        return None


class IsPerfectURLVisible(IsVisible):
    def get_object(self, request):
        url = self.get_or_set_url(request=request).perfect
        if url is None:
            return
        try:
            return url.urlvisible
        except URLVisible.DoesNotExist:
            return None


class IsImperfectURLVisible(IsVisible):
    """
    Allows for '/a/b/c/' to be hidden because '/a/b/' is marked as not
    published
    """
    def get_object(self, request):
        url = self.get_or_set_url(request=request).imperfect
        if url is None:
            return None
        url = URL(path=request.path)
        url.full_clean()
        possibilities = url.get_path_ancestry(include_self=True)
        best_url = (URLVisible.objects.filter(url__path__in=possibilities)
                    .order_by('-url__path').first())
        return best_url


class NeedsRedirecting(RequestURL):
    def get_object(self, request):
        url = self.get_or_set_url(request=request).imperfect
        try:
            return url.urlredirect
        except URLRedirect.DoesNotExist:
            return None

    def process_request(self, request):
        if self.is_excluded():
            return None
        obj = self.get_object(request=request)
        if obj is not None:
            location = obj.get_absolute_url()
            if obj.is_permanent:
                return HttpResponsePermanentRedirect(location)
            return HttpResponseRedirect(location)
        return None
