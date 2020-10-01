#!/usr/bin/env python3

import asyncio
import discord
import json
import os
import traceback
import factorio_rcon
from dotenv import load_dotenv

load_dotenv()

CHANNEL = int(os.getenv('DISCORD_CHANNEL'))
STATUS_FREQUENCY = int(os.getenv('STATUS_FREQUENCY') or '0')

# obsolete in python 3.9
def removesuffix(text, prefix):
    return text[:-len(prefix)] if text.endswith(prefix) else text

class RecoveringRCON:
    rcon = None
    connecting = False
    version = None

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
                self.version = self.rcon.send_command('/version')
            except ConnectionError:
                #print('connection failed, retrying in 2 seconds')
                await asyncio.sleep(2)
            else:
                await self.onmsg({ 'type': 'connected', 'version': self.version })
                self.connecting = False
                break

    async def send(self, msg):
        try:
            self.rcon.send_command(msg)
        except ConnectionError:
            await self.connect()
        return None

    async def get_players(self):
        return [removesuffix(line.strip(), ' (online)') for line in self.rcon.send_command('/players online').splitlines()[1:]]

    async def get_player_status(self):
        try:
            players = await self.get_players()
            return '{} {} online'.format(len(players), 'player' if len(players) == 1 else 'players')
        except ConnectionError:
            return None

    async def get_server_status(self):
        try:
            players = await self.get_players()
            return 'Version {} - Online players ({}): {}'.format(self.version, len(players), ', '.join(players))
        except ConnectionError:
            return 'Offline'

    async def poll(self):
        while True:
            if self.rcon is not None:
                try:
                    for msg in json.loads(self.rcon.send_command('/fadmin poll')):
                        await self.onmsg(msg)
                except ConnectionError:
                    await self.onmsg({ 'type': 'disconnected' })
                    await self.connect()
            await asyncio.sleep(.5)

def main():
    rcon = RecoveringRCON(os.getenv('RCON_HOST'), int(os.getenv('RCON_PORT')), os.getenv('RCON_PWD'))

    client = discord.Client()

    since_last_update = 0

    async def background():
        await client.wait_until_ready()
        channel = client.get_channel(CHANNEL)

        async def onmsg(msg):
            try:
                if msg['type'] == 'connected':
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions('*Server is online (' + msg['version'] + ')*')))
                elif msg['type'] == 'disconnected':
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions('*Server is offline*')))
                elif msg['type'] == 'chat':
                    str = msg['name'] + ': ' + msg['message']
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                elif msg['type'] == 'left':
                    p = await rcon.get_player_status()
                    str = '*' + msg['name'] + ' left' + (' - ' + p if p else '') + '*'
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                elif msg['type'] == 'joined':
                    p = await rcon.get_player_status()
                    str = '*' + msg['name'] + ' joined' + (' - ' + p if p else '') + '*'
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                elif msg['type'] == 'died':
                    cause = None
                    if msg.get('cause', None) == None:
                        cause = ' died of mysterious causes'
                    elif msg['cause']['type'] == 'locomotive':
                        cause = ' was squished by a rogue train'
                    elif msg['cause']['type'] == 'character':
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
                        cause = f' was killed by {msg["cause"]["type"]}'

                    str = '*' + msg['name'] + cause + '*'
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                elif msg['type'] == 'promoted':
                    pass # do nothing as it fires upon player joining for first time and not at time of promotion which makes it meaningless
                elif msg['type'] == 'demoted':
                    pass
                elif msg['type'] == 'kicked':
                    str = '*{name} was kicked by {by_player}{r}*'.format(r=f': {msg["reason"]}' if msg.get('reason') else '', **msg)
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                elif msg['type'] == 'banned':
                    str = '*{name} was banned by {by_player}{r}*'.format(r=f': {msg["reason"]}' if msg.get('reason') else '', **msg)
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                elif msg['type'] == 'unbanned':
                    str = '*{name} was unbanned by {by_player}{r}*'.format(r=f': {msg["reason"]}' if msg.get('reason') else '', **msg)
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                else:
                    print(msg)
            except Exception:
                traceback.print_exc()

        @client.event
        async def on_ready():
            print('Logged in as')
            print(client.user.name)
            print(client.user.id)
            print('------')

        @client.event
        async def on_message(message):
            if message.channel.id != CHANNEL:
                return

            nonlocal since_last_update
            since_last_update += 1
            if STATUS_FREQUENCY != 0 and since_last_update > STATUS_FREQUENCY:
                since_last_update = 0
                asyncio.ensure_future(channel.send(discord.utils.escape_mentions('*' + await rcon.get_server_status() + '*')))

            if message.author == client.user:
                return
            name = message.author.nick or message.author.name
            await rcon.send('/fadmin chat ' + name + '*: ' + message.clean_content)

        rcon.onmsg = onmsg
        await rcon.connect()
        await rcon.poll()


    try:
        task = client.loop.create_task(background())
        client.loop.run_until_complete(client.start(os.getenv('DISCORD_TOKEN')))
    except KeyboardInterrupt:
        task.cancel()
        client.loop.run_until_complete(client.logout())
    finally:
        client.loop.close()
