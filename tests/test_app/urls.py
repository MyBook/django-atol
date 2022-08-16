from django.urls import re_path
from atol.views import ReceiptView

urlpatterns = [
    re_path(r'^r/(?P<short_uuid>[\w]+)/$', ReceiptView.as_view(), name='receipt'),
]
