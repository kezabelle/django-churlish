import re
import logging
from collections import namedtuple
from itertools import product
from django.conf import settings
from django.utils.functional import cached_property
from django.http import (Http404, HttpResponseRedirect,
                         HttpResponsePermanentRedirect)
from django.core.urlresolvers import reverse_lazy, NoReverseMatch
from django.contrib import admin
from django.contrib.sites.models import Site
from .models import URL, URLVisible, URLRedirect

try:
    from django.utils.timezone import now
except ImportError:
    from datetime import datetime
    now = datetime.now


logger = logging.getLogger(__name__)


URLData = namedtuple('URLData', 'perfect imperfect all path')


class RequestURL(object):
    """
    API for figuring out whether the request should proceed to the DB,
    and what it should ask for
    """
    __slots__ = ('test_collector',)

    def __init__(self, test_collector=None):
        self.test_collector = test_collector

    def get_prefetch_related(self, request):
        if self.test_collector is None:
            return ()
        relations = self.test_collector.get_relations()
        return tuple(relations)

    def get_select_related(self, request):
        if self.test_collector is None:
            return ()
        relations = self.test_collector.get_relations()
        return tuple(relations)

    def get_query_set(self, request, instance):
        prefetches = self.get_prefetch_related(request=request)
        selects = self.get_select_related(request=request)
        qs = instance.get_ancestors(include_self=True).filter(
            site=Site.objects.get_current())
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

    def request_is_excluded(self, request):
        compiled_exclusions = frozenset(re.compile(x, re.VERBOSE) 
                                        for x in self.get_exclusions())
        for exclusion in compiled_exclusions:
            if exclusion.search(request.path):
                return True
        return False


class RequestTesters(object):
    """
    Serves as an API around discovery of middleware partials, currently
    using the URL ModelAdmin, maybe using a separate registry in future.
    """
    __slots__ = ()

    def get_modeladmin(self, request=None):
        try:
            return admin.site._registry[URL]
        except KeyError:
            # Not mounted into the admin, so we can't figure out which
            # relations might affect the URL instances.
            logger.error("Unable to use ChurlishMiddleware because the"
                         "the admin site doesn't have a URL Modeladmin "
                         "instance", exc_info=1)
            return None

    def get_tests(self, request=None):
        urladmin = self.get_modeladmin(request=request)
        if urladmin is None:
            return None
        try:
            return urladmin.get_middlewares()
        except AttributeError:
            logger.error("Unable to use ChurlishMiddleware because the "
                         "admin site doesn't implement the `get_middlewares`"
                         "method", exc_info=1)
            return None
    
    def get_relations(self, request=None):
        return self.get_modeladmin(request=request).get_runtime_relations()


class ChurlishMiddleware(object):
    __slots__ = ()

    def process_view(self, request, view_func, view_args, view_kwargs):
        test_collector = RequestTesters()
        url_handler = RequestURL(test_collector=test_collector)
        logextra = {'request': request}
        logcls = self.__class__.__name__
        if url_handler.request_is_excluded(request=request):
            logger.debug("Skipping {cls!s} for this request as it matches "
                         "a configured exclusion".format(cls=logcls),
                         extra=logextra)
            return None  # no match, so continue with other middlewares
        request.churlish = url_handler.get_url_data(request=request)
        if len(request.churlish.all) < 1:
            logger.debug("Skipping {cls!s} for this request because no URLs "
                         "match any path components".format(cls=logcls),
                         extra=logextra)
            return None   # no match, so continue with other middlewares

        bound_mws = test_collector.get_tests(request=request)
        urls_and_mws = product(request.churlish.all, bound_mws)

        errors = []
        for url, mw in urls_and_mws:
            logger.debug("Running {cls!s} against {url!s}".format(
                cls=mw.__class__.__name__, url=url.path), extra=logextra)

            status = mw.test(request=request, obj=url, view=view_func)

            if status is None:
                logger.debug("{cls!s} is not applicable for {url!s}".format(
                    cls=mw.__class__.__name__, url=url.path), extra=logextra)
                continue

            # make True worth 0 points, False worth 1. Keeps our tally for 
            # checking the sum later.
            # None is skipped because of the `continue` statement previously.
            errors.append(int(not status))

            if status is True and hasattr(mw, 'success'):
                response = mw.success(request=request, obj=url, view=view_func)
                if response is not None:
                    logger.debug("{cls!s} forced {url!s} to return".format(
                        cls=mw.__class__.__name__, url=url.path),
                        extra=logextra)
                    return response
            elif status is False and hasattr(mw, 'error'):
                response = mw.error(request=request, obj=url, view=view_func)
                if response is not None:
                    logger.debug("{cls!s} forced {url!s} to return".format(
                        cls=mw.__class__.__name__, url=url.path),
                        extra=logextra)
                    return response

        # we should only hit this condition if a test failed, but didn't try
        # to handle it's business by implemementing .error() as a response
        # or an exception.
        if sum(errors) > 0:
            logger.warning("One of the ChurlishMiddleware partials said the "
                           "request should fail, but did not opt to handle "
                           " the response.", extra=logextra)
            raise Http404("Request failed tests for this URL")
