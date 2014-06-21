from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.settings import api_settings
from .serializers import URLSerializer
from .models import URL


class URLPageViewSet(viewsets.ModelViewSet):
    queryset = URL.objects.all()
    serializer_class = URLSerializer
    paginate_by = api_settings.PAGINATE_BY or 10
    paginate_by_param = api_settings.PAGINATE_BY_PARAM or 'page'


class SaferURLPageViewSet(mixins.CreateModelMixin,
                          mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin,
                          mixins.ListModelMixin,
                          viewsets.GenericViewSet):
    queryset = URLPageViewSet.queryset
    serializer_class = URLPageViewSet.serializer_class
    paginate_by = URLPageViewSet.paginate_by
    paginate_by_param = URLPageViewSet.paginate_by_param
