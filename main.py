#!/usr/bin/env python3

import json
import os
import socket
import sys
from time import sleep
from construct import *
from dotenv import load_dotenv

load_dotenv()

packet = Prefixed(Int32sl, Struct(
    'id' / Int32sl,
    'type' / Int32sl,
    'body' / CString("utf8"),
    Default(CString("utf8"), '')
))

def parse_data(str):
    data = json.loads(str)
    for msg in data:
        print(msg)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.connect((os.getenv('RCON_HOST'), int(os.getenv('RCON_PORT'))))
    file = sock.makefile('rwb')

    file.write(packet.build({'id': 0, 'type': 3, 'body': os.getenv('RCON_PWD')}))
    file.flush()

    while True:
        file.write(packet.build({'id': 2, 'type': 2, 'body': '/sc remote.call("fadmin", "poll")'}))
        file.flush()
        p = packet.parse_stream(file)
        if p.type == 0 and p.id == 2:
            parse_data(p.body)
        sleep(1)
