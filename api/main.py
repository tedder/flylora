#!/usr/bin/env python3

import quart

import base64
import datetime
import json
import os
import struct

#from pymongo import MongoClient
import pymongo
import bson.json_util
import bson
import requests
import haversine

import logging

# set root level details
logging.basicConfig(
        level=logging.INFO,
        style='{',
        format='{asctime} | {levelname:<8} | {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        )

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = quart.Quart(__name__)
def get_database():
    # Provide the mongodb atlas url to connect python to mongodb using pymongo
    # Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
    db = pymongo.MongoClient(os.environ['MONGODB_CONNSTRING'])
    # Create the database for our example (we will use the same database throughout the tutorial
    return db['helium_test']

@app.route("/hello")
async def hello():
  return 'hello.'

@app.route("/helloj")
async def helloj():
  db = get_database()
  collection = db["device_pings"]
  cc = json.loads( json.dumps(list( collection.find({}) ), default=bson.json_util.default) )
  #cc = bson.decode( collection.find({})[0] )

  return {'hello': 'world', 'c': cc }

async def parse_helium_post(data):
  ret = {}
  ret['hotspot_count'] = len(data.get("hotspots", []))
  decoded_payload = base64.b64decode(data["payload"])
  logger.info(f"decoded payload: {decoded_payload}")
  print(f"decoded payload: {decoded_payload}")
  (lat,lon,x) = decoded_payload.split(b",")
  lat = float(lat)
  lon = float(lon)
  print(f"llx: {lat}, {lon}, {x}; type lat: {type(lat)}")

  ret["hotspot_distances"] = []
  for h in data.get('hotspots', []):
    dist = haversine.haversine( (lat, lon), (h["lat"], h["long"]), unit=haversine.Unit.MILES)
    ret["hotspot_distances"].append(dist)

  return ret

def intmile(m):
  # taking a mile as a float, make it into an int*100
  # in other words, 3.456 will be 345
  logger.info(f"intmile: {m} // {m*100} // {int(m*100)}")
  return int(m*100)

@app.route("/ping", methods=["GET","POST"])
@app.route("/ping/", methods=["GET","POST"])
async def ping():
  print(f"form: {await quart.request.form}")
  data = await quart.request.get_json()

  # data is a dict
  print(f"json data: {type(data)} {data}")
  helium_data = await parse_helium_post(data)

  if data.get("downlink_url"):
    print(f'downlink url: {data["downlink_url"]}')

    # payload fmt, 1 byte
    # placeholders, 3 bytes
    # received_at time, epoch, 4 bytes (this won't work after 2032 lol)
    # hotspot count, 1 byte
    # min rx distance in miles*100, 2 bytes
    # max rx distance in miles*100, 2 bytes
    min_rx_dist = intmile( min(helium_data["hotspot_distances"]) )
    max_rx_dist = intmile( max(helium_data["hotspot_distances"]) )
    rx_time_epoch = int( datetime.datetime.utcnow().timestamp() )
    print(f"tx values: {rx_time_epoch} {helium_data['hotspot_count']} {min_rx_dist} {max_rx_dist}")

    tx_payload = struct.pack('!BBBBLBHH', 1, 0,0,0, rx_time_epoch, helium_data['hotspot_count'], min_rx_dist, max_rx_dist)
    tx_payload_encoded = base64.b64encode(tx_payload)

    print(f"tx_payload: {tx_payload}; encoded: {tx_payload_encoded}")
    #rxtime_encoded = base64.b64encode(rec['received_at'].encode('ascii')).decode('ascii')
    #print(f"RXT: {rxtime_encoded}")
    r = requests.post(data.get("downlink_url"), json={"payload_raw": tx_payload_encoded.decode() })
    print(f"post: {r.status_code} {r.text}")
  return {"ack": 0}


def foo():
  rec = {}

  db = get_database()
  collection = db["device_pings"]
  rec["received_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  if data.get("payload"):
    try:
      rec["payload_decoded"] = json.loads(base64.b64decode(data["payload"]))
    except json.decoder.JSONDecodeError:
      rec["payload_decoded"] = {"error": "Couldn't parse as JSON"}
    rec["iteration"] = rec["payload_decoded"].get("i")
    rec["session_id"] = rec["payload_decoded"].get("s")
    if ll := rec["payload_decoded"].get("ll"):
      print(f"haz ll: {ll}")
    collection.insert_one(rec)
  if data.get("downlink_url"):
    rxtime_encoded = base64.b64encode(rec['received_at'].encode('ascii')).decode('ascii')
    print(f"RXT: {rxtime_encoded}")
    r = requests.post(data.get("downlink_url"), json={"payload_raw": rxtime_encoded})
    print(f"post: {r.status_code}")
  return {"ack": rec["received_at"]}

app.run(host='0.0.0.0', debug=True)
