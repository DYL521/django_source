from django.utils.deprecation import MiddlewareMixin


class CustomMiddle(MiddlewareMixin):
    def process_request(self, request):
        print(request)
        """
        返回值是None的话，按正常流程继续走，交给下一个中间件处理，
        如果是HttpResponse对象，Django将不执行视图函数，而将相应对象返回给浏览器。
        """

    def process_response(self, response):
        """
        返回的必须是HttpRespons对象
        """
        pass

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        request是HttpRequest对象。
        view_func是Django即将使用的视图函数。（它是实际的函数对象，而不是函数的名称作为字符串。）
        view_args是将传递给视图的位置参数的列表。
        view_kwargs是将传递给视图的关键字参数的字典。 view_args和view_kwargs都不包含第一个视图参数（request）。
        """
        pass

    def process_exception(self, request, exception):
        """
        这个方法只有在视图函数中出现异常了才执行，它返回的值可以是一个None也可以是一个HttpResponse对象。
        如果是HttpResponse对象，Django将调用模板和中间件中的process_response方法，并返回给浏览器，否则将默认处理异常
        """
        pass

    def process_template_response(self, request, response):
        pass
