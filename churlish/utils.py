from .models import URL


def get_perfect_urlmatch(path):
    try:
        return URL.objects.get(path__iexact=path)
    except URL.DoesNotExist:
        return None


def get_imperfect_urlmatch(path):
    url = URL(path=path)
    url.full_clean()
    possibilities = url.get_path_ancestry(include_self=True)
    urls = URL.objects.filter(path__in=possibilities)
    return urls.first()  # may return None
