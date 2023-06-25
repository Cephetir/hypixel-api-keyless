import uvicorn
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, PlainTextResponse
import re
import requests
from json import JSONDecoder, JSONEncoder
from threading import Thread, Lock
import time

currentKeyIndex = 0
lock = Lock()
app = FastAPI()


@app.get("/status", response_class=PlainTextResponse, description="Check if API is operational", summary="API Status")
def status():
    return "OK"


@app.get("/favicon.ico")
def icon():
    return JSONResponse(None, status_code=404)


@app.get("/", description="All requests will be redirected to official Hypixel API", summary="Hypixel API")
async def api(request: Request):
    if request.url.path == "/key":
        return JSONResponse({}, status_code=404)
    key = getKey()
    if key == "key":
        return JSONResponse({"success": False, "reason": "All available keys are ratelimited!"}, status_code=429)
    hypixelResp = requests.get("https://api.hypixel.net" + request.url.path + "?key=" + key + "&" + request.url.query)
    if "Content-Encoding" in hypixelResp.headers.keys():
        hypixelResp.headers.pop("Content-Encoding")
    if "ratelimit-remaining" in hypixelResp.headers.keys():
        setKey(int(hypixelResp.headers["ratelimit-remaining"]), int(hypixelResp.headers["ratelimit-reset"]))
    resp = JSONResponse(hypixelResp.json(), hypixelResp.status_code, hypixelResp.headers)
    return resp


def getKey() -> str:
    global currentKeyIndex
    global lock
    lock.acquire(blocking=True, timeout=-1)
    file = open("keys.json", "r")
    keys = list(JSONDecoder().decode(file.read()))
    file.close()

    total = len(keys)
    if total <= 0:
        return "key"
    if currentKeyIndex >= total:
        currentKeyIndex = 0

    key = None
    tries = 0
    while key is None and tries <= total:
        key = keys[currentKeyIndex]
        if key["disabled"]:
            key = None
        currentKeyIndex += 1
        if currentKeyIndex >= total:
            currentKeyIndex = 0
        tries += 1
    if key is None:
        return "key"
    lock.release()
    return key["key"]


def setKey(remaining: int, reset: int):
    if remaining > 2:
        return

    global currentKeyIndex
    global lock
    lock.acquire(blocking=True, timeout=-1)
    file = open("keys.json", "r")
    keys = list(JSONDecoder().decode(file.read()))
    file.close()

    key = keys[currentKeyIndex]
    key["disabled"] = True

    file = open("keys.json", "w")
    file.write(JSONEncoder().encode(keys))
    file.close()
    lock.release()

    Thread(target=reenable, args=[reset, currentKeyIndex]).start()


def reenable(reset: int, index: int):
    time.sleep(reset)
    lock.acquire(blocking=True, timeout=-1)
    file = open("keys.json", "r")
    keys = list(JSONDecoder().decode(file.read()))
    file.close()

    key = keys[index]
    key["disabled"] = False

    file = open("keys.json", "w")
    file.write(JSONEncoder().encode(keys))
    file.close()
    lock.release()


for route in app.routes:
    if isinstance(route, APIRoute) and route.name == "api":
        route.path_regex = re.compile("/.+")

if __name__ == "__main__":
    uvicorn.run(app, port=3330)
