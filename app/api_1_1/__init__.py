from flask import Blueprint

api11 = Blueprint('api11', __name__)

from . import api_server
