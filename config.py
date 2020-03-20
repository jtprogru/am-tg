#!/usr/bin/env python
# coding=utf-8
# Created by JTProgru / JTProg
# Date: 18.03.2020
# https://jtprog.ru/

__author__ = 'jtprog'
__version__ = '0.0.1'
__author_email__ = 'mail@jtprog.ru'

import os


class ConfigMap:
    SECRET_KEY = 'CHANGEME'
    TG_TOKEN = os.getenvb('TG_TOKEN')
    TG_CHAT_ID = os.getenvb('TG_CHAT_ID')
    DEBUG = True
    BASIC_AUTH_USERNAME = os.getenvb('BA_UNAME')
    BASIC_AUTH_PASSWORD = os.getenvb('BA_UPASS')
    BASIC_AUTH_FORCE = True
    LOG_FILE = '/var/log/am-tg.log'
