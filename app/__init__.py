import os
import urllib
import logging
import json

from logging import FileHandler
from flask import request
from flask import jsonify
from flask import Flask
from flask import Blueprint
#from flask.ext.login import LoginManager

from .common.dao import DAO

#login_manager = LoginManager()
db = DAO()

def create_app():
    flask = Flask(__name__)
    try:
        flask.config.from_pyfile(os.path.dirname(__file__) + '/config.py')
        print "importing configuration from config.py"
    except:
        print "config.py not found."
        exit()
    logging_path = os.path.dirname(__file__) + '/../logs/debug.log'
    file_handler = FileHandler(logging_path, 'a')
    file_handler.setLevel(logging.DEBUG)
    flask.logger.addHandler(file_handler)
    flask.logger.info("logger set up")
    #login_manager.init_app(flask)
    db.init_app(flask)
    from .api_1_0 import api as api_1_0_blueprint
    flask.register_blueprint(api_1_0_blueprint, url_prefix='/api/v1.0')
    from .api_1_1 import api11 as api_1_1_blueprint
    flask.register_blueprint(api_1_1_blueprint, url_prefix='/api/v1.1')
    return flask

