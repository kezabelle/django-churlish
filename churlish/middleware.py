import logging
from collections import namedtuple
from django.http import (Http404, HttpResponseRedirect,
                         HttpResponsePermanentRedirect)
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


class IsVisible(object):
    """
    Allows for '/a/b/c/' to be hidden only when it is explicitly marked
    as unpublished
    """
    def get_object(self, request):
        raise NotImplementedError

    def process_request(self, request):
        url = self.get_object()
        if url is None:
            return None  # no match, so continue with other middlewares
        return self.handle_unpublished(url=url, request=request)

    def is_unpublished(self, url, request):
        if not url.is_pubished:
            msg = ("URL (pk: {url}) has publishing information (pk: {vis}) "
                   "which prevents it from being displayed now "
                   "({now})".format(url=url.url_id, vis=url.pk, now=now()))
            logger.error(msg, extra={'request': request, 'status_code': 404})
            raise Http404("URL is marked as unpublished explicitly")
        return None


class IsPerfectURLVisible(IsVisible):
    def get_object(self, request):
        try:
            return URLVisible.objects.get(url__path=request.path)
        except URLVisible.DoesNotExist:
            return None


class IsImperfectURLVisible(IsVisible):
    """
    Allows for '/a/b/c/' to be hidden because '/a/b/' is marked as not
    published
    """
    def get_object(self, request):
        url = URL(path=request.path)
        url.full_clean()
        possibilities = url.get_path_ancestry(include_self=True)
        best_url = (URLVisible.objects.filter(url__path__in=possibilities)
                    .order_by('-url__path').first())
        return best_url


class NeedsRedirecting(object):
    def get_object(self, request):
        try:
            URLRedirect.objects.get(url__path=request.path)
        except URLRedirect.DoesNotExist:
            return None

    def process_request(self, request):
        obj = self.get_object(request=request)
        if obj is not None:
            location = obj.get_absolute_url()
            if obj.is_permanent:
                return HttpResponsePermanentRedirect(location)
            return HttpResponseRedirect(location)
        return None
