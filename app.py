from flask import Flask, Response, request
from config import ConfigMap
from flask_basicauth import BasicAuth
from utils import *
import logging

app = Flask(__name__)
app.config.from_object(ConfigMap)

basic_auth = BasicAuth(app)


@app.route('/alert', methods=['POST'])
def alert():
    content = json.loads(str(request.get_data().decode("utf-8")))
    print(content)
    with open("output.txt", "w") as text_file:
        text_file.write("{0}".format(content))
    try:
        message = prep_msg(content)
        print('[*] Returned message: \n {}'.format(message))

        print(post_to_tg(msg=message, chat_id=app.config['TG_CHAT_ID'], tg_token=app.config['TG_TOKEN']))
        return "Alert OK", 200
    except:
        print(post_to_tg(msg="<b>Broken data</b>", chat_id=app.config['TG_CHAT_ID'], tg_token=app.config['TG_TOKEN']))
        return "Alert NotOK", 200


@app.route('/')
def hello_world():
    return 'Hello World!\n'


@app.route("/favicon.ico")
def favicon():
    return Response('FUCK YOU', 200, mimetype='image/x-icon')


if __name__ == '__main__':
    logging.basicConfig(filename=ConfigMap.LOG_FILE, level=logging.DEBUG)
    app.run(host='127.0.0.1', port=9119)
