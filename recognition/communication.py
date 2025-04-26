#!/usr/bin/env python3

from uuid import uuid5, getnode, NAMESPACE_DNS, NAMESPACE_URL
from random import random, choice
from zoneinfo import available_timezones
from requests import post
from time import time
from recognition.signature_format import DecodedMessage
from recognition.user_agent import USER_AGENTS

_locale = 'en-US'
_first_uuid = str(uuid5(NAMESPACE_DNS, str(getnode()))).upper()
_second_uuid = str(uuid5(NAMESPACE_URL, str(getnode())))
_timezones = [tz for tz in available_timezones() if tz.startswith('Europe/')]

def recognise_song_from_signature(signature: DecodedMessage) -> dict:
    fuzz = random() * 15.3 - 7.65

    altitude = random() * 400 + 100 + fuzz
    latitude = random() * 180 - 90 + fuzz
    longitude = random() * 360 - 180 + fuzz
    timestamp_ms = int(time() * 1000)

    return post(
        f'https://amp.shazam.com/discovery/v5/en/US/android/-/tag/{_first_uuid}/{_second_uuid}',
        params={
            'sync': 'true',
            'webv3': 'true',
            'sampling': 'true',
            'connected': '',
            'shazamapiversion': 'v3',
            'sharehub': 'true',
            'video': 'v3'
        },
        headers={
            'Content-Type': 'application/json',
            'User-Agent': choice(USER_AGENTS),
            'Content-Language': _locale
        },
        json={
            "geolocation": {
                "altitude": altitude,
                "latitude": latitude,
                "longitude": longitude
            },
            "signature": {
                "samplems": int(signature.number_samples / signature.sample_rate_hz * 1000),
                "timestamp": timestamp_ms,
                "uri": signature.encode_to_uri()
            },
            "timestamp": timestamp_ms,
            "timezone": choice(_timezones)
        }
    ).json()