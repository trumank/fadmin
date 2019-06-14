#!/usr/bin/env python3

import asyncio
import discord
import json
import os
import factorio_rcon
from dotenv import load_dotenv

load_dotenv()

CHANNEL = int(os.getenv('DISCORD_CHANNEL'))

class RecoveringRCON:
    rcon = None

    connecting = False

    def __init__(self, host, port, pwd, onmsg=None):
        self.host = host
        self.port = port
        self.pwd = pwd

        self.onmsg = onmsg

    async def connect(self):
        if self.connecting:
            return
        self.connecting = True
        while True:
            try:
                self.rcon = factorio_rcon.RCONClient(self.host, self.port, self.pwd)
                version = self.rcon.send_command('/version')
            except ConnectionError:
                #print('connection failed, retrying in 2 seconds')
                await asyncio.sleep(2)
            else:
                await self.onmsg({ 'type': 'connected', 'version': version })
                self.connecting = False
                break

    async def send(self, msg):
        try:
            self.rcon.send_command(msg)
        except ConnectionError:
            await self.connect()
        return None

    async def poll(self):
        while True:
            if self.rcon is not None:
                try:
                    for msg in json.loads(self.rcon.send_command('/fadmin poll')):
                        await self.onmsg(msg)
                except ConnectionError:
                    await self.onmsg({ 'type': 'disconnected' })
                    await self.connect()
            await asyncio.sleep(.1)

def main():
    rcon = RecoveringRCON(os.getenv('RCON_HOST'), int(os.getenv('RCON_PORT')), os.getenv('RCON_PWD'))

    client = discord.Client()

    async def my_background_task():
        await client.wait_until_ready()
        channel = client.get_channel(CHANNEL)

        async def onmsg(msg):
            if msg['type'] == 'connected':
                asyncio.ensure_future(channel.send('*Server is online (' + msg['version'] + ')*'))
            elif msg['type'] == 'disconnected':
                asyncio.ensure_future(channel.send('*Server is offline*'))
            elif msg['type'] == 'chat':
                str = msg['name'] + ': ' + msg['message']
                asyncio.ensure_future(channel.send(str))
            elif msg['type'] == 'left':
                str = '*' + msg['name'] + ' left*'
                asyncio.ensure_future(channel.send(str))
            elif msg['type'] == 'joined':
                str = '*' + msg['name'] + ' joined*'
                asyncio.ensure_future(channel.send(str))
            elif msg['type'] == 'died':
                cause = None
                if msg.get('cause', None) == None:
                    cause = ' died of mysterious causes'
                elif msg['cause']['type'] == 'locomotive':
                    cause = ' was squished by a rogue train'
                elif msg['cause']['type'] == 'player':
                    if msg['cause']['player'] == msg['name']:
                        cause = ' lost their will to live'
                    else:
                        cause = ' was brutally murdered by ' + msg['cause']['player']
                elif msg['cause']['type'] == 'tank':
                    cause = ' was hiding in a tank\'s blind spot'
                elif msg['cause']['type'] == 'car':
                    cause = ' was involved in a hit and run'
                elif msg['cause']['type'] == 'artillery-turret':
                    cause = ' was mistaken for the enemy'
                else:
                    cause = ' died of mysterious causes'

                str = '*' + msg['name'] + cause + '*'
                asyncio.ensure_future(channel.send(str))
            else:
                print(msg)

        rcon.onmsg = onmsg
        await rcon.connect()
        await rcon.poll()

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
        await rcon.send('/fadmin chat ' + name + '*: ' + message.content)

    try:
        task = client.loop.create_task(my_background_task())
        client.loop.run_until_complete(client.start(os.getenv('DISCORD_TOKEN')))
    except KeyboardInterrupt:
        task.cancel()
        client.loop.run_until_complete(client.logout())
    finally:
        client.loop.close()
