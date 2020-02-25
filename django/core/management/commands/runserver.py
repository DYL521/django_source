import errno
import os
import re
import socket
import sys
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.servers.basehttp import (
    WSGIServer, get_internal_wsgi_application, run,
)
from django.utils import autoreload

naiveip_re = re.compile(r"""^(?:
(?P<addr>
    (?P<ipv4>\d{1,3}(?:\.\d{1,3}){3}) |         # IPv4 address
    (?P<ipv6>\[[a-fA-F0-9:]+\]) |               # IPv6 address
    (?P<fqdn>[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*) # FQDN
):)?(?P<port>\d+)$""", re.X)


class Command(BaseCommand):
    help = "Starts a lightweight Web server for development."

    # Validation is called explicitly each time the server is reloaded.
    requires_system_checks = False
    leave_locale_alone = True
    stealth_options = ('shutdown_message',)

    default_addr = '127.0.0.1'  # 默认ip地址
    default_addr_ipv6 = '::1'
    default_port = '8000'  # 默认端口
    protocol = 'http'  # 默认协议
    server_cls = WSGIServer

    def add_arguments(self, parser):
        parser.add_argument(
            'addrport', nargs='?',
            help='Optional port number, or ipaddr:port'
        )
        parser.add_argument(
            '--ipv6', '-6', action='store_true', dest='use_ipv6',
            help='Tells Django to use an IPv6 address.',
        )
        # 调试时，去掉多线程运行
        parser.add_argument(
            '--nothreading', action='store_false', dest='use_threading',
            help='Tells Django to NOT use threading.',
        )
        # 代码修改的时候不会自动重载
        parser.add_argument(
            '--noreload', action='store_false', dest='use_reloader',
            help='Tells Django to NOT use the auto-reloader.',
        )

    def execute(self, *args, **options):
        if options['no_color']:
            # We rely on the environment because it's currently the only
            # way to reach WSGIRequestHandler. This seems an acceptable
            # compromise considering `runserver` runs indefinitely.
            os.environ["DJANGO_COLORS"] = "nocolor"
        super().execute(*args, **options)

    def get_handler(self, *args, **options):
        """Return the default WSGI handler for the runner."""
        return get_internal_wsgi_application()

    def handle(self, *args, **options):
        from django.conf import settings
        # 设置一些属性值，如果有在命令行中指定就用命令中的参数，不然就用默认值。
        if not settings.DEBUG and not settings.ALLOWED_HOSTS:  # 如果DEBUG is False，必须设置ALLOWED_HOSTS
            raise CommandError('You must set settings.ALLOWED_HOSTS if DEBUG is False.')

        self.use_ipv6 = options['use_ipv6']
        if self.use_ipv6 and not socket.has_ipv6:
            raise CommandError('Your Python does not support IPv6.')
        self._raw_ipv6 = False
        if not options['addrport']:
            self.addr = ''
            self.port = self.default_port
        else:
            m = re.match(naiveip_re, options['addrport'])
            if m is None:
                raise CommandError('"%s" is not a valid port number '
                                   'or address:port pair.' % options['addrport'])
            self.addr, _ipv4, _ipv6, _fqdn, self.port = m.groups()
            if not self.port.isdigit():
                raise CommandError("%r is not a valid port number." % self.port)
            if self.addr:
                if _ipv6:
                    self.addr = self.addr[1:-1]
                    self.use_ipv6 = True
                    self._raw_ipv6 = True
                elif self.use_ipv6 and not _fqdn:
                    raise CommandError('"%s" is not a valid IPv6 address.' % self.addr)
        if not self.addr:
            self.addr = self.default_addr_ipv6 if self.use_ipv6 else self.default_addr
            self._raw_ipv6 = self.use_ipv6
        # 设置完属性之后，真正运行服务器
        self.run(**options)

    def run(self, **options):
        """Run the server, using the autoreloader if needed."""
        use_reloader = options['use_reloader']

        if use_reloader:  # 如果要使用自动重载
            autoreload.main(self.inner_run, None, options)
        else:
            self.inner_run(None, **options)

    def inner_run(self, *args, **options):
        # If an exception was silenced in ManagementUtility.execute in order
        # to be raised in the child process, raise it now.
        autoreload.raise_last_exception()

        # 根据命令参数，输出对应的内容，进行标准输出
        threading = options['use_threading']
        # 'shutdown_message' is a stealth option.
        shutdown_message = options.get('shutdown_message', '')
        quit_command = 'CTRL-BREAK' if sys.platform == 'win32' else 'CONTROL-C'

        self.stdout.write("Performing system checks...\n\n")
        import pdb;
        pdb.set_trace()
        self.check(display_num_errors=True)  # 静态检查工具，解释行语言的毛病
        # Need to check migrations here, so can't use the
        # requires_migrations_check attribute.
        self.check_migrations()  # 检查migrations文件。。。输出一些提示
        now = datetime.now().strftime('%B %d, %Y - %X')
        self.stdout.write(now)
        self.stdout.write((
                              "Django version %(version)s, using settings %(settings)r\n"
                              "Starting development server at %(protocol)s://%(addr)s:%(port)s/\n"
                              "Quit the server with %(quit_command)s.\n"
                          ) % {
                              "version": self.get_version(),
                              "settings": settings.SETTINGS_MODULE,
                              "protocol": self.protocol,
                              "addr": '[%s]' % self.addr if self._raw_ipv6 else self.addr,
                              "port": self.port,
                              "quit_command": quit_command,
                          })
        # try里面才是真正跑项目服务的，跑起来之后才能接收请求。
        try:
            # handler是默认的WSGI协议的处理器，其实就是django里面封装好的处理器
            handler = self.get_handler(*args, **options)
            # 可以看出这个已经是服务器内部实现的函数的，所以直到这一步，runsever命令的服务才真正被启动并等待接收请求。
            run(self.addr, int(self.port), handler,
                ipv6=self.use_ipv6, threading=threading, server_cls=self.server_cls)
        except socket.error as e:
            # Use helpful error messages instead of ugly tracebacks.
            ERRORS = {
                errno.EACCES: "You don't have permission to access that port.",
                errno.EADDRINUSE: "That port is already in use.",
                errno.EADDRNOTAVAIL: "That IP address can't be assigned to.",
            }
            try:
                error_text = ERRORS[e.errno]
            except KeyError:
                error_text = e
            self.stderr.write("Error: %s" % error_text)
            # Need to use an OS exit because sys.exit doesn't work in a thread
            os._exit(1)
        except KeyboardInterrupt:
            if shutdown_message:
                self.stdout.write(shutdown_message)
            sys.exit(0)


# Kept for backward compatibility
BaseRunserverCommand = Command
