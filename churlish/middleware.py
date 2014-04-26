import logging
from django.http import Http404
from .models import URL, URLVisible

try:
    from django.utils.timezone import now
except ImportError:
    from datetime import datetime
    now = datetime.now


logger = logging.getLogger(__name__)


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
