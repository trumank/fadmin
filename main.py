#!/usr/bin/env python3

import asyncio
import discord
import json
import os
import socket
import sys
import threading
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

CHANNEL = int(os.getenv('DISCORD_CHANNEL'))

def run():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((os.getenv('RCON_HOST'), int(os.getenv('RCON_PORT'))))
        file = sock.makefile('rwb')

        file.write(packet.build({'id': 0, 'type': 3, 'body': os.getenv('RCON_PWD')}))
        file.flush()

        async def poll():
            while True:
                file.write(packet.build({'id': 2, 'type': 2, 'body': '/sc remote.call("fadmin", "poll")'}))
                file.flush()
                p = await client.loop.run_in_executor(None, packet.parse_stream(file))
                if p.type == 0 and p.id == 2:
                    for msg in json.loads(p.body):
                        yield msg
                await asyncio.sleep(1)

        client = discord.Client()

        async def my_background_task():
            await client.wait_until_ready()
            counter = 0
            channel = client.get_channel(CHANNEL)
            async for msg in poll():
                if not client.is_closed:
                    break;
                str = ''
                if msg['type'] == 'chat':
                    str = msg['name'] + ': ' + msg['message']
                await channel.send(str)

        @client.event
        async def on_ready():
            print('Logged in as')
            print(client.user.name)
            print(client.user.id)
            print('------')

        @client.event
        async def on_message(message):
            if message.author == client.user or message.channel.id != CHANNEL:
                return
            name = message.author.nick or message.author.name
            str = '"' + (name + '*: ' + message.content).replace('\\', '\\\\').replace('"', '\\"') + '"';
            file.write(packet.build({'id': 3, 'type': 2, 'body': '/sc game.print(' + str + ', {.7,.7,.7})'}))
            file.flush()

        client.loop.create_task(my_background_task())
        client.run(os.getenv('DISCORD_TOKEN'))

run()

