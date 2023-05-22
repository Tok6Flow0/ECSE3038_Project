from fastapi import FastAPI, HTTPException, Request
from bson import ObjectId
import motor.motor_asyncio
from fastapi.middleware.cors import CORSMiddleware
import pydantic
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import uvicorn
import json
import requests
import pytz
import re

reference_temp = 28.0

app = FastAPI()

load_dotenv()
client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv('MONGO_CONNECTION_STRING'))
db = client.statedb
db2 = client.settingsdb

pydantic.json.ENCODERS_BY_TYPE[ObjectId] = str

origins = ["https://simple-smart-hub-client.netlify.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/state", status_code=201)
async def set_state(request: Request):
    state = await request.json()
    state["datetime"] = (datetime.now() + timedelta(hours=-5)).strftime('%Y-%m-%dT%H:%M:%S')
    new_state = await db["states"].insert_one(state)
    updated_state = await db["states"].find_one({"_id": new_state.inserted_id })
    if new_state.acknowledged == True:
        return updated_state
    raise HTTPException(status_code=400, detail="Issue")

@app.get("/api/state")
async def get_state():
    current_state = await db["states"].find().sort("datetime", -1).to_list(1)
    current_settings = await db["settings"].find().to_list(1)
    presence = current_state[0]["presence"]
    
    timenow = datetime.strptime(datetime.strftime(datetime.now() + timedelta(hours=-5), '%Y-%m-%dT%H:%M:%S'), '%Y-%m-%dT%H:%M:%S')
    user_light = datetime.strptime(current_settings[0]["user_light"], '%Y-%m-%dT%H:%M:%S')
    light_off = datetime.strptime(current_settings[0]["light_time_off"], '%Y-%m-%dT%H:%M:%S')

    fan_state = ((float(current_state[0]["temperature"]) > float(current_settings[0]["user_temp"])) and presence)
    light_state = (timenow > user_light) and (presence) and (timenow < light_off)

    print(datetime.strftime(datetime.now() + timedelta(hours=-5), '%Y-%m-%dT%H:%M:%S'))
    print(current_settings[0]["user_light"])
    print(current_settings[0]["light_time_off"])
    print(presence)

    dictionary = {"fan": fan_state, "light": light_state}
    return dictionary

def sunset():
    sunset_response = requests.get(f'https://api.sunrise-sunset.org/json?lat=18.1096&lng=-77.2975&date=today')
    sunset_json = sunset_response.json()
    sunset_timedate = sunset_json["results"]["sunset"]
    sunset_timedate = datetime.strptime(sunset_timedate, '%I:%M:%S %p') + timedelta(hours=-5)
    sunset_timedate = datetime.strftime(sunset_timedate, '%H:%M:%S')
    return sunset_timedate

@app.get("/graph", status_code=200)
async def graph_points(request: Request, size: int):
    n = size
    state_array = await db["states"].find().sort("datetime", -1).to_list(n)
    state_array.reverse()
    return state_array

@app.put("/settings", status_code=200)
async def setting(request: Request):
    setting = await request.json()
    elements = await db["settings"].find().to_list(1)
    mod_setting = {}
    mod_setting["user_temp"] = setting["user_temp"]
    if setting["user_light"] == "sunset":
        timestring = sunset()
    else:
        timestring = setting["user_light"]

    mod_setting["user_light"] = ((datetime.now() + timedelta(hours=-5)).date()).strftime("%Y-%m-%dT") + timestring
    mod_setting["light_time_off"] = ((datetime.strptime(mod_setting["user_light"], '%Y-%m-%dT%H:%M:%S') + parse_time(setting["light_duration"])).strftime('%Y-%m-%dT%H:%M:%S'))
    print(mod_setting["user_light"])
    print(mod_setting["light_time_off"])

    if len(elements) == 0:
         new_setting = await db["settings"].insert_one(mod_setting)
         patched_setting = await db["settings"].find_one({"_id": new_setting.inserted_id })
         return patched_setting
    else:
        id = elements[0]["_id"]
        updated_setting = await db["settings"].update_one({"_id": id}, {"$set": mod_setting})
        patched_setting = await db["settings"].find_one({"_id": id})
        if updated_setting.modified_count >= 1:
            return patched_setting
    raise HTTPException(status_code=400, detail="Issue")

regex = re.compile(r'((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')

def parse_time(time_str):
    parts = regex.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)