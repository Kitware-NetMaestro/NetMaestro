from django.http import HttpRequest, HttpResponse
from django.template import loader


def home(request: HttpRequest) -> HttpResponse:
    template = loader.get_template('index.html')
    return HttpResponse(template.render(request=request))
