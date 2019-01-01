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

from . import api11 as api
from .. import db

from ..common.point_in_polygon import wn_PnPoly 
from ..common.helper import validate_client 
from ..common.ca_qtree import *

# TODO - generalize code for multiple states
@api.route('/find_in_state', methods=['POST'])
def find_in_state():
    filename = os.path.dirname(__file__) + '/../../files/ca_papers.csv'

    if not validate_client(request.remote_addr,
                           current_app.config['KNOWN_CLIENTS']):
        current_app.logger.error('access denied')
        return jsonify({'message':'access denied'}),500

    json_obj = request.get_json()
    if json_obj is None:
        current_app.logger.error('arguments missing')
        return jsonify({'message':'arguments missing'}),500

    state = json_obj.get('state')

    try:
        conn = db.make_connection()
    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60
        return jsonify({'message':'Error occurred while trying to connect to the database'}),500

    try:
        cursor = conn.cursor()

        query = "SELECT n.name, c.lat, c.lon, n.email from Newspaper n JOIN City c ON c.city_id=n.city_id and c.state='%s'"
        cursor.execute(query % (state))
        rows = cursor.fetchall()

    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60
        return jsonify({'message':'Error occurred while accessing the database'}),500
    finally:
        if cursor:
            cursor.close()
        conn.close()
 
    # Start with an area larger than California to be safe.
    root = Node(None, 32.275814, -124.564671, 42.117975, -114.236181)
    init_qtree(root, rows)

    editors = get_from_state(root)
    editors_obj = [{'name' : e[2], 'email' : e[3]} for e in editors]
        #'city' : findLocationByPoint([e[1], e[0]])} for e in editors]

    return jsonify({'message' : 'success', 'data' : editors_obj}),201

@api.route('/find_editors', methods=['POST'])
def find_editors():
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
    county = json_obj.get('county')
    distance = json_obj.get('distance')
    county_opt = json_obj.get('county_only')

    county_opt = county_opt if county_opt else 'true'
    county_only = county_opt == 'true'

    if not county:
        county = getCounty(city)

    editors = getEditors(city, county, distance, county_only)

    return jsonify({'message' : 'success', 'data' : editors}),201

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
    include_county = json_obj.get('include_county')
    if street:
      street = street.replace(".","")

    point,county = getGeoPoint(state, zipcode, city, street)
    if point is None:
        return jsonify({'message':'Could not locate the address.'}),201
    legislators = getLegislators(state, point)
    if not ("Senate" in legislators['legislators'] or "Assembly" in legislators['legislators']):
        return jsonify({'message':'Could not find legislators.'}),201

    if county:
        legislators['county'] = county

    return jsonify({'message':'success','data':legislators}),201

@api.route('/locate_address', methods=['POST'])
def locate_address():
    address = None
    '''
    if not validate_client(request.remote_addr,
                           current_app.config['KNOWN_CLIENTS']):
        current_app.logger.error('access denied')
        return jsonify({'message':'access denied'}),500
    '''
    json_obj = request.get_json()
    if json_obj is None:
        current_app.logger.error('arguments missing')
        return jsonify({'message':'arguments missing'}),500

    point = json_obj.get('point')
    print point
    address = findLocationByPoint(point)
    if not address:
        return jsonify({'message':'Could not locate address.'}),201
    return jsonify({'message':'success','data':address}),201

def getGeoPoint(state, zipcode, city, street):
    point = None
    county = None
    url = "https://dev.virtualearth.net/REST/v1/Locations/US/%s/%s/%s/%s?o=json&key=%s"
    try:
        print url % (state,zipcode,urllib.quote(city),urllib.quote(street),
                        current_app.config['API_KEY'])
        response = requests.get(url %
                       (state,zipcode,urllib.quote(city),urllib.quote(street),
                        current_app.config['API_KEY']))
        current_app.logger.debug(response)
        content = json.loads(response.content)

        estimated_total = content['resourceSets'][0]['estimatedTotal']
        for resource in content['resourceSets'][0]['resources']:
            if estimated_total > 1 and resource['confidence'] != 'High':
                continue
            #latitude, longitude
            point = [resource['point']['coordinates'][1],
                     resource['point']['coordinates'][0]]
            county = resource['address']['adminDistrict2']
       
        print point

    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60

    if point is None:
        current_app.logger.warning("no point returned from Bing!")
    return point,county 

def getEditors(city, county, dist, county_only=True):
    editors = []
    conn = None

    try:
        conn = db.make_connection()
    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60
        return editors
 
    try:
        cursor = conn.cursor()

        # get the county id
        if county:
            query = "SELECT county_id,name from County WHERE name='%s'"
            cursor.execute(query % (county))
        else:
            query = """SELECT c.county_id,co.name from City c
                       JOIN County co ON c.county_id=co.county_id WHERE c.name='%s'
                    """
            cursor.execute(query % (city))

        # get all the editors within the county
        county_id,county = cursor.fetchone()

        if county_only:
            query = """SELECT n.name, c.lat, c.lon, n.email from Newspaper n,
                       City c WHERE n.city_id=c.city_id AND c.county_id=%s"""
            cursor.execute(query % (county_id))
        else:
            query = "SELECT n.name, c.lat, c.lon, n.email from Newspaper n, City c WHERE n.city_id=c.city_id"
            cursor.execute(query)

        rows = cursor.fetchall()

        # Start with an area larger than California to be safe.
        root = Node(None, 32.275814, -124.564671, 42.117975, -114.236181)
        init_qtree(root, rows)

        # Get the city coordinates
        query = "SELECT lat, lon from City WHERE name='%s'"
        cursor.execute(query % (city))
        result = cursor.fetchone()

        # Get the nearest editors
        nearest_editors = get_nearest_cities(root, result[0], result[1], dist)

        for ne in nearest_editors:
            editors.append({'name' : ne[2], 'email' : ne[3]})
    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60
    finally:
        conn.close()

    return editors

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
        curr_year = int(time.strftime("%Y"))
        # convert even year to previous odd year, which is the session year
        curr_year = curr_year - (1 - curr_year % 2)
 
        query = """SELECT p.pid,last,first,middle,email_form_link,email,
                   capitol_fax,party
                   from Person p 
                   JOIN Term t ON p.pid=t.pid AND
                   t.year=%s AND t.state='%s' AND t.house='%s' AND t.district=%s
                   JOIN Legislator l ON l.pid = p.pid"""

        cursor.execute(query % (curr_year,state,'Senate',district['Senate']))
        pid, last, first, middle, email_form_link, email, fax, party = cursor.fetchone()
        legislators['Senate'] = {
            'district':district['Senate'], 'pid':pid, 'last':last,
            'first':first, 'middle': middle,
            'email_form_link':email_form_link, 'email':email,
            'fax':fax, 'party':party
        }

        cursor.execute(query % (curr_year,state,'Assembly',district['Assembly']))
        pid, last, first, middle, email_form_link, email, fax, party = cursor.fetchone()
        legislators['Assembly'] = {
            'district':district['Assembly'], 'pid':pid, 'last':last,
            'first':first, 'middle': middle,
            'email_form_link':email_form_link, 'email':email,
            'fax':fax, 'party':party
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

def findLocationByPoint(point):
    address = None 
    url = "http://dev.virtualearth.net/REST/v1/Locations/%s,%s?key=%s"
    try:
        response = requests.get(url %
                       (point[1],point[0],
                        current_app.config['API_KEY']))
        current_app.logger.debug(response)
        content = json.loads(response.content)

        for resource in content['resourceSets'][0]['resources']:
            if resource['confidence'] != 'High':
                continue
            #latitude, longitude
            address = resource['address']
    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60

    if address is None:
        current_app.logger.warning("no address returned from Bing!")
    return address 

def getCounty(city):
    conn = None
    county = None
    county_id = None

    try:
        conn = db.make_connection()
    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60
        return editors

    try:
        cursor = conn.cursor()
        query = """SELECT c.county_id,co.name from City c
                   JOIN County co ON c.county_id=co.county_id WHERE c.name='%s'
                """
        cursor.execute(query % (city))
        county_id,county = cursor.fetchone()
        cursor.close()
    except:
        print "Exception in user code:"
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error(traceback.print_exc(file=sys.stdout))
        print '-'*60
    finally:
        conn.close()

    return county

