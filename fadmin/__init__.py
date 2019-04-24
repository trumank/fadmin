#!/usr/bin/env python3

import asyncio
import discord
import json
import os
import sys
import threading
import factorio_rcon
from time import sleep
from dotenv import load_dotenv

load_dotenv()

CHANNEL = int(os.getenv('DISCORD_CHANNEL'))

def run():
    rcon = factorio_rcon.RCONClient(os.getenv('RCON_HOST'), int(os.getenv('RCON_PORT')), os.getenv('RCON_PWD'))

    async def poll():
        while True:
            for msg in json.loads(rcon.send_command('/sc remote.call("fadmin", "poll")')):
                yield msg
            await asyncio.sleep(.1)

    client = discord.Client()

    async def my_background_task():
        await client.wait_until_ready()
        counter = 0
        channel = client.get_channel(CHANNEL)
        async for msg in poll():
            if not client.is_closed:
                break;
            if msg['type'] == 'chat':
                str = msg['name'] + ': ' + msg['message']
                asyncio.ensure_future(channel.send(str))
            if msg['type'] == 'left':
                str = '*' + msg['name'] + ' left*'
                asyncio.ensure_future(channel.send(str))
            if msg['type'] == 'joined':
                str = '*' + msg['name'] + ' joined*'
                asyncio.ensure_future(channel.send(str))

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
        escaped = '"' + (name + '*: ' + message.content).replace('\\', '\\\\').replace('"', '\\"') + '"';
        rcon.send_command('/sc game.print(' + escaped + ', {.7,.7,.7})')

    client.loop.create_task(my_background_task())
    client.run(os.getenv('DISCORD_TOKEN'))

run()

