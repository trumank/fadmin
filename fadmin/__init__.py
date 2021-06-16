#!/usr/bin/env python3

import asyncio
import discord
import json
import os
import traceback
import factorio_rcon
import prometheus_client
import prometheus_client.core
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
    connected = False
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
                self.connected = True
                self.connecting = False
                break

    async def send(self, msg):
        try:
            return self.rcon.send_command(msg)
        except ConnectionError:
            self.connected = False
            await self.connect()
        return None

    async def get_players(self):
        return [removesuffix(line.strip(), ' (online)') for line in self.rcon.send_command('/players online').splitlines()[1:]]

    async def get_player_status(self):
        try:
            players = await self.get_players()
            return f"{len(players)} {'player' if len(players) == 1 else 'players'}"
        except ConnectionError:
            self.connected = False
            return None

    async def get_server_status(self):
        try:
            players = await self.get_players()
            return f"Version {self.version} - Online players ({len(players)}): {', '.join(players)}"
        except ConnectionError:
            self.connected = False
            return 'Offline'

    async def poll(self):
        while True:
            if self.rcon is not None:
                try:
                    for msg in json.loads(self.rcon.send_command('/fadmin poll')):
                        await self.onmsg(msg)
                except ConnectionError:
                    self.connected = False
                    await self.onmsg({ 'type': 'disconnected' })
                    await self.connect()
            await asyncio.sleep(.5)

class GameCollector:
    def __init__(self, rcon, loop):
        self.rcon = rcon
        self.loop = loop

    def collect(self):
        if not self.rcon.connected:
            return []

        try:
            result = asyncio.run_coroutine_threadsafe(self.rcon.send('/fadmin stats'), self.loop).result()
            if not result:
                return []
            stats = json.loads(result)
        except Exception as err:
            print(err)
            return []

        gametick = prometheus_client.core.GaugeMetricFamily(
            'factorio_game_ticks_total', 'Game tick map has progressed to.', value=stats['game_tick'])
        players = prometheus_client.core.GaugeMetricFamily(
            'factorio_player_count', 'Amount of players connected to the server.', value=stats['player_count'])

        force_flows = prometheus_client.core.CounterMetricFamily(
            'factorio_force_flow_statistics', 'Items/fluids/enemies/buildings produced/consumed/built/killed by a force',
            labels=['force', 'statistic', 'direction', 'name'])

        game_flows  = prometheus_client.core.CounterMetricFamily(
            'factorio_game_flow_statistics', 'Pollution produced/consumed in the game', labels=['statistic', 'direction', 'name'])

        force_flow_metrics = set()
        for force_name, flow_statistics in stats['force_flow_statistics'].items():
            for statistic_name, statistic in flow_statistics.items():
                for direction, counts in statistic.items():
                    for item, value in counts.items():
                        labels = (force_name, statistic_name, direction, item)
                        force_flows.add_metric(labels, value)
                        force_flow_metrics.add(labels)

        # For item and fluid statistics it's useful to compare the input flow with the
        # output flow, to simplify the comparison ensure both directions have a value.
        for labels in force_flow_metrics:
            force_name, statistic_name, direction, item = labels
            if statistic_name in ["item_production_statistics", "fluid_production_statistic"]:
                direction = "output" if direction == "input" else "input"
                labels = (force_name, statistic_name, direction, item)
                if not labels in force_flow_metrics:
                    force_flows.add_metric(labels, 0)

        for direction, counts in stats['game_flow_statistics']['pollution_statistics'].items():
            for item, value in counts.items():
                game_flows.add_metric(["pollution_statistics", direction, item], value)

        return [gametick, players, force_flows, game_flows]

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
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(f"*Server is online ({msg['version']})*")))
                elif msg['type'] == 'disconnected':
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions('*Server is offline*')))
                elif msg['type'] == 'chat':
                    str = f"{msg['name']}: {msg['message']}"
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                elif msg['type'] == 'left':
                    p = await rcon.get_player_status()
                    str = f"*{msg['name']} left{' - ' + p if p else ''}*"
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                elif msg['type'] == 'joined':
                    p = await rcon.get_player_status()
                    str = f"*{msg['name']} joined{' - ' + p if p else ''}*"
                    asyncio.ensure_future(channel.send(discord.utils.escape_mentions(str)))
                elif msg['type'] == 'died':
                    text = {
                        None: ' died of mysterious causes',
                        'locomotive': ' was squished by a rogue train',
                        'cargo-wagon': ' tried to sneak under a moving train',
                        'fluid-wagon': ' tried to rob a train of it\'s oil',
                        'tank': ' was hiding in a tank\'s blind spot',
                        'car': ' was involved in a hit and run',
                        'artillery-turret': ' was mistaken for the enemy',
                        'spidertron': ' has a serious case of arachnophobia'
                        # 'behemoth-biter': '',
                        # 'big-biter': '',
                        # 'medium-biter': '',
                        # 'small-biter': '',
                        # 'behemoth-spitter': '',
                        # 'big-spitter': '',
                        # 'medium-spitter': '',
                        # 'small-spitter': '',
                        # 'behemoth-worm-turret': '',
                        # 'big-worm-turret': '',
                        # 'medium-worm-turret': '',
                        # 'small-worm-turret': '',
                    }
                    cause = None
                    if msg.get('cause', None) in text:
                        cause = text[msg['cause']['type']]
                    elif msg['cause']['type'] == 'character':
                        if msg['cause']['player'] == msg['name']:
                            cause = ' lost their will to live'
                        else:
                            cause = f" was brutally murdered by {msg['cause']['player']}"
                    else:
                        cause = f" was killed by a {msg['cause']['type']}"

                    str = f"*{msg['name']}{cause}*"
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
                asyncio.ensure_future(channel.send(discord.utils.escape_mentions(f"*{await rcon.get_server_status()}*")))

            if message.author == client.user:
                return
            name = message.author.nick or message.author.name
            await rcon.send(f"/fadmin chat {name}*: {message.clean_content}")

        rcon.onmsg = onmsg
        await rcon.connect()
        await rcon.poll()


    def factorio_pid():
        try:
            with open(os.getenv('FACTORIO_PIDFILE')) as f:
                return f.read()
        except OSError:
            return 'bad_pidfile'

    factorio_process = prometheus_client.ProcessCollector('factorio', factorio_pid)
    prometheus_client.REGISTRY.register(GameCollector(rcon, client.loop))
    prometheus_client.start_http_server(int(os.getenv('PROMETHEUS_PORT')), os.getenv('PROMETHEUS_HOST'))

    try:
        task = client.loop.create_task(background())
        client.loop.run_until_complete(client.start(os.getenv('DISCORD_TOKEN')))
    except KeyboardInterrupt:
        task.cancel()
        client.loop.run_until_complete(client.logout())
    finally:
        client.loop.close()
