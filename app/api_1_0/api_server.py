#!/usr/bin/python

import os
import sys
import traceback
import re
import requests 
import urllib
#import current_app.logger
import json
import MySQLdb
#import multiprocessing as mp
#import subprocess
import time

#from threading import Timer
#from current_app.logger import FileHandler
from flask import request
from flask import jsonify
from flask import Flask
from flask import Blueprint
from flask import current_app
from ast import literal_eval as make_tuple

from . import api
from .. import db

from ..common.point_in_polygon import wn_PnPoly 
from ..common.helper import validate_client 

@api.route('/find_legislators', methods=['POST'])
def find_district():
    legislators = None
    if not validate_client(request.remote_addr,
                           current_app.config['KNOWN_CLIENTS']):
        current_app.logger.error('access denied')
        return jsonify({'message':'access denied'}),500

    json_obj = request.get_json()
    if json_obj is None:
        current_app.logger.error('arguments missing')
        return jsonify({'message':'arguments missing'}),500

    state = json_obj.get('state')
    zipcode = json_obj.get('zipcode')
    city = json_obj.get('city')
    street = json_obj.get('street')

    point = getGeoPoint(state, zipcode, city, street)
    if point is None:
        return jsonify({'message':'Could not locate the address.'}),201
    legislators = getLegislators(state, point)
    if not ("Senate" in legislators or "Assembly" in legislators):
        return jsonify({'message':'Could not find legislators.'}),201
    return jsonify({'message':'success','data':legislators}),201

def getGeoPoint(state, zipcode, city, street):
    point = None
    url = "https://dev.virtualearth.net/REST/v1/Locations/US/%s/%s/%s/%s?o=json&key=%s"
    try:
        response = requests.get(url %
                       (state,zipcode,urllib.quote(city),urllib.quote(street),
                        current_app.config['API_KEY']))
        current_app.logger.debug(response)
        content = json.loads(response.content)

        for resource in content['resourceSets'][0]['resources']:
            if resource['confidence'] != 'High':
                continue
            #latitude, longitude
            point = [resource['point']['coordinates'][1],
                     resource['point']['coordinates'][0]]

    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60

    if point is None:
        current_app.logger.warning("no point returned from Bing!")
    return point 

def getLegislators(state, point):
    legislators = {} 
    conn = None
    try:
        conn = db.make_connection()
    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60
        return legislators
 
    try:
        cursor = conn.cursor()
    
        query = "SELECT state,house,did,geoData from District WHERE state='%s'"
        cursor.execute(query % (state))
        recs = cursor.fetchall()
        district={}
        for state,house,did,geoData in recs:
            #current_app.logger.info(state,house,did)
            geoData = geoData.replace("{","(")
            geoData = geoData.replace("}",")")
            tup = make_tuple(geoData)
            v = list(tup)
            result = wn_PnPoly(point, v)
            #current_app.logger.info(result)
            if result != 0:
                district[house]=did
        current_app.logger.debug(district)
        curr_year = time.strftime("%Y")
 
        query = """SELECT p.pid,last,first,middle,email_form_link,email from Person p 
                   JOIN Term t ON p.pid=t.pid AND
                   t.year=%s AND t.state='%s' AND t.house='%s' AND t.district=%s
                   JOIN Legislator l ON l.pid = p.pid"""

        cursor.execute(query % (curr_year,state,'Senate',district['Senate']))
        pid, last, first, middle, email_form_link, email = cursor.fetchone()
        legislators['Senate'] = {
            'district':district['Senate'], 'pid':pid, 'last':last,
            'first':first, 'middle': middle,
            'email_form_link':email_form_link, 'email':email
        }

        cursor.execute(query % (curr_year,state,'Assembly',district['Assembly']))
        pid, last, first, middle, email_form_link, email = cursor.fetchone()
        legislators['Assembly'] = {
            'district':district['Assembly'], 'pid':pid, 'last':last,
            'first':first, 'middle': middle,
            'email_form_link':email_form_link, 'email':email
        }
    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60
    finally:
        conn.close()

    return {'legislators':legislators, 'geo_coord': point}
 
