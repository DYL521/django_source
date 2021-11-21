#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # 设置环境变量
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myprojetc.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # 执行将用户传入的参数传入到内部执行 ： Python manage.py runserver :  runserver 就会作为参数传入内部
    logger.info("step:1 {}".format(sys.argv))
    execute_from_command_line(sys.argv)

