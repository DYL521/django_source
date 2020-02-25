"""
HTTP server that implements the Python WSGI protocol (PEP 333, rev 1.21).

Based on wsgiref.simple_server which is part of the standard library since 2.5.

This is a simple server for use in testing or debugging Django apps. It hasn't
been reviewed for security issues. DON'T USE IT FOR PRODUCTION USE!
"""

import logging
import socket
import socketserver
import sys
from wsgiref import simple_server

from django.core.exceptions import ImproperlyConfigured
from django.core.wsgi import get_wsgi_application
from django.utils.module_loading import import_string

__all__ = ('WSGIServer', 'WSGIRequestHandler')

logger = logging.getLogger('django.server')


def get_internal_wsgi_application():
    """
    Load and return the WSGI application as configured by the user in
    ``settings.WSGI_APPLICATION``. With the default ``startproject`` layout,
    this will be the ``application`` object in ``projectname/wsgi.py``.

    This function, and the ``WSGI_APPLICATION`` setting itself, are only useful
    for Django's internal server (runserver); external WSGI servers should just
    be configured to point to the correct application object directly.

    If settings.WSGI_APPLICATION is not set (is ``None``), return
    whatever ``django.core.wsgi.get_wsgi_application`` returns.
    """
    from django.conf import settings
    app_path = getattr(settings, 'WSGI_APPLICATION')
    if app_path is None:
        return get_wsgi_application()

    try:
        return import_string(app_path)
    except ImportError as err:
        raise ImproperlyConfigured(
            "WSGI application '%s' could not be loaded; "
            "Error importing module." % app_path
        ) from err


def is_broken_pipe_error():
    exc_type, exc_value = sys.exc_info()[:2]
    return issubclass(exc_type, socket.error) and exc_value.args[0] == 32


class WSGIServer(simple_server.WSGIServer):
    """BaseHTTPServer that implements the Python WSGI protocol"""

    request_queue_size = 10

    def __init__(self, *args, ipv6=False, allow_reuse_address=True, **kwargs):
        if ipv6:
            self.address_family = socket.AF_INET6
        self.allow_reuse_address = allow_reuse_address
        super().__init__(*args, **kwargs)

    def handle_error(self, request, client_address):
        if is_broken_pipe_error():
            logger.info("- Broken pipe from %s\n", client_address)
        else:
            super().handle_error(request, client_address)


class ThreadedWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    """A threaded version of the WSGIServer"""
    pass


class ServerHandler(simple_server.ServerHandler):
    http_version = '1.1'

    def handle_error(self):
        # Ignore broken pipe errors, otherwise pass on
        if not is_broken_pipe_error():
            super().handle_error()


class WSGIRequestHandler(simple_server.WSGIRequestHandler):
    protocol_version = 'HTTP/1.1'

    def address_string(self):
        # Short-circuit parent method to not call socket.getfqdn
        return self.client_address[0]

    def log_message(self, format, *args):
        extra = {
            'request': self.request,
            'server_time': self.log_date_time_string(),
        }
        if args[1][0] == '4':
            # 0x16 = Handshake, 0x03 = SSL 3.0 or TLS 1.x
            if args[0].startswith('\x16\x03'):
                extra['status_code'] = 500
                logger.error(
                    "You're accessing the development server over HTTPS, but "
                    "it only supports HTTP.\n", extra=extra,
                )
                return

        if args[1].isdigit() and len(args[1]) == 3:
            status_code = int(args[1])
            extra['status_code'] = status_code

            if status_code >= 500:
                level = logger.error
            elif status_code >= 400:
                level = logger.warning
            else:
                level = logger.info
        else:
            level = logger.info

        level(format, *args, extra=extra)

    def get_environ(self):
        # Strip all headers with underscores in the name before constructing
        # the WSGI environ. This prevents header-spoofing based on ambiguity
        # between underscores and dashes both normalized to underscores in WSGI
        # env vars. Nginx and Apache 2.4+ both do this as well.
        for k, v in self.headers.items():
            if '_' in k:
                del self.headers[k]

        return super().get_environ()

    def handle(self):
        """Copy of WSGIRequestHandler.handle() but with different ServerHandler"""
        self.raw_requestline = self.rfile.readline(65537)
        if len(self.raw_requestline) > 65536:
            self.requestline = ''
            self.request_version = ''
            self.command = ''
            self.send_error(414)
            return

        if not self.parse_request():  # An error code has been sent, just exit
            return

        handler = ServerHandler(
            self.rfile, self.wfile, self.get_stderr(), self.get_environ()
        )
        handler.request_handler = self  # backpointer for logging
        handler.run(self.server.get_app())


def run(addr, port, wsgi_handler, ipv6=False, threading=False, server_cls=WSGIServer):
    server_address = (addr, port)
    if threading:
        httpd_cls = type('WSGIServer', (socketserver.ThreadingMixIn, server_cls), {})
    else:
        httpd_cls = server_cls
    httpd = httpd_cls(server_address, WSGIRequestHandler, ipv6=ipv6)
    if threading:
        # ThreadingMixIn.daemon_threads indicates how threads will behave on an
        # abrupt shutdown; like quitting the server by the user or restarting
        # by the auto-reloader. True means the server will not wait for thread
        # termination before it quits. This will make auto-reloader faster
        # and will prevent the need to kill the server manually if a thread
        # isn't terminating correctly.
        httpd.daemon_threads = True
    httpd.set_app(wsgi_handler)
    # ## 真正启动服务器，然后等待请求并处理
    httpd.serve_forever()

    """
    首先，我们了解了django项目的入口程序其实就是manage.py通过对命令行参数进行解析，然后对不同的命令进行不同的处理。
针对runserver（django项目启动），其实最最关键的地方就在于django/__init__.py中的setup函数，
在这里先设置了url解析的前缀，让开发者既可以自定义，也可以在开发过程中的urls.py中不用添加前置'/'，
接下来就是对于所有app的相关配置。
app的相关配置有两个关键部分，一个是对单个app的配置类AppConfig，一个是对所有app的管理类Apps，这两个类紧密相关，是总分关系，同时相互索引。在初始化过程中，Apps在控制流程，主要包括对所有app进行路径解析、名字去重、对每个app配置类进行初始化、赋予每个app配置类它们的相关models、还有就是执行每个app开发者自己定义的ready函数。
在真正执行runserver命令的部分，我们可以看到是用了fetch_command函数拿到对应命令的Command类，然后再调用BaseCommand类中的run_from_argv函数。通过这一部分，我们可以更好地了解到为什么自定义命令的时候需要在app中创建management目录和commands目录，为什么Command类需要继承BaseCommand类，为什么Command类中需要实现一个handle函数，这些都是从源码到用法的验证。
从整个runserver命令的流程上看，最主要的就是两个部分，一个是setup去做app相关的配置和检查，搞定之后，就找到真正的handle函数去做服务的拉起和接收请求，这样runserver的使命就算是完成了。

https://zhuanlan.zhihu.com/p/97316210


execute_from_command_line()
    utility.execute()
		--->django.setup()
	self.fetch_command('runserver').run_from_argv(self.argv)
		--->fetch_command('runserver') 返回对应命令模块的类的实例，这里是'runserver'命令的类
		--->run_from_argv(self.argv)
			--->execute()做一些设置参数的错误检查，然后设置句柄
				--->handle()做些设置
					--->run() 主要调用inner_run，区分是否是use_reloader
						--->inner_run()
								--->inner_run() 设置句柄handler,WSGIHandler 的实例
									---run(handler...)一个标准的 wsgi 实现

"""
