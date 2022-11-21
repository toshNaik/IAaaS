import functions_framework
import imgaug

@functions_framework.http
def hello(request):
    return 'Hello world!'