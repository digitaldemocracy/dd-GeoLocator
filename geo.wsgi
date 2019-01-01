#!/usr/bin/python
import sys
sys.path.insert(0, '/var/www/dd-GeoService')
from app import create_app
application = create_app()
