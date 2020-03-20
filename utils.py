#!/usr/bin/env python
# coding=utf-8
# Created by JTProgru / JTProg
# Date: 18.03.2020
# https://jtprog.ru/

__author__ = 'jtprog'
__version__ = '0.0.1'
__author_email__ = 'mail@jtprog.ru'

import json
import requests


def post_to_tg(msg, chat_id, tg_token):
    endpoint_url = "https://api.telegram.org/bot{}/sendMessage".format(tg_token)
    json_headers = {"Content-Type": "application/json; charset=UTF-8"}
    form_data = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    json_data = json.dumps(form_data, indent=1, sort_keys=True)
    resp = requests.post(endpoint_url, data=json_data, headers=json_headers)
    print('[*] Resp status code: {}'.format(resp.status_code))
    return resp.status_code


def prep_msg(m):
    message = ''
    for alert in m['alerts']:
        message = """<b>Status</b>: """ + alert['status'] + """\n"""
        message += """Alertname: """ + alert['labels']['alertname'] + """ \n"""
        if alert['status'] == "firing":
            message += """Detected: """ + alert['startsAt'] + """ \n"""
        if alert['status'] == "resolved":
            message += """Resolved: """ + alert['endsAt'] + """ \n"""
        if 'name' in alert['labels']:
            message += """Instance: """ + alert['labels']['instance'] + """(""" + alert['labels']['name'] + """) \n"""
        else:
            message += """Instance: """ + alert['labels']['instance'] + """ \n"""
        message += """View URL: <a href="https://prometheus.example.com/""" + \
                   alert['generatorURL'].split('/')[-1] + "\">Link to Prom</a>" + """"""
        message += """<b>Annotations</b>\n\n""" + alert['annotations']['description'] + """"""

    return str(message)

