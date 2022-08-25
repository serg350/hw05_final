from django.core.paginator import Paginator

POSTS_ON_PAGE = 10


def get_page_context(const, request):
    paginator = Paginator(const, POSTS_ON_PAGE)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)
