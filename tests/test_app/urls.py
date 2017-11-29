from django.conf.urls import url
from atol.views import ReceiptView

urlpatterns = [
    url(r'^r/(?P<short_uuid>[\w]+)/$', ReceiptView.as_view(), name='receipt'),
]
