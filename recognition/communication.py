#!/usr/bin/python3

from uuid import uuid5, getnode, NAMESPACE_DNS, NAMESPACE_URL
from random import seed, random, choice
from pytz import all_timezones
from requests import post
from time import time

from recognition.signature_format import DecodedMessage
from recognition.user_agent import USER_AGENTS

locale = ('en_US').split('.')[0]

first_uuid = str(uuid5(NAMESPACE_DNS, str(getnode()))).upper()
second_uuid = str(uuid5(NAMESPACE_URL, str(getnode())))

def recognise_song_from_signature(signature : DecodedMessage) -> dict:

    fuzz = random() * 15.3 - 7.65

    seed(getnode())

    return post('https://amp.shazam.com/discovery/v5/en/US/android/-/tag/' + first_uuid + '/' + second_uuid, params = {
        'sync': 'true',
        'webv3': 'true',
        'sampling': 'true',
        'connected': '',
        'shazamapiversion': 'v3',
        'sharehub': 'true',
        'video': 'v3'
    }, headers = {
        'Content-Type': 'application/json',
        'User-Agent': choice(USER_AGENTS),
        'Content-Language': locale
    }, json = {
        "geolocation": {
            "altitude": random() * 400 + 100 + fuzz,
            "latitude": random() * 180 - 90 + fuzz,
            "longitude": random() * 360 - 180 + fuzz
        },
        "signature": {
            "samplems": int(signature.number_samples / signature.sample_rate_hz * 1000),
            "timestamp": int(time() * 1000),
            "uri": signature.encode_to_uri()
        },
        "timestamp": int(time() * 1000),
        "timezone": choice([timezone for timezone in all_timezones if 'Europe/' in timezone])
    }).json()