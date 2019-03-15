local util = require("util")
local silo_script = require("silo-script")

local created_items = function()
  return
  {
    ["iron-plate"] = 8,
    ["wood"] = 1,
    ["pistol"] = 1,
    ["firearm-magazine"] = 10,
    ["burner-mining-drill"] = 1,
    ["stone-furnace"] = 1
  }
end

local respawn_items = function()
  return
  {
    ["pistol"] = 1,
    ["firearm-magazine"] = 10
  }
end

for k,v in pairs(silo_script.get_events()) do
  script.on_event(k, v)
end

script.on_event(defines.events.on_player_created, function(event)
  local player = game.players[event.player_index]
  util.insert_safe(player, global.created_items)

  local r = global.chart_distance or 200
  player.force.chart(player.surface, {{player.position.x - r, player.position.y - r}, {player.position.x + r, player.position.y + r}})

  if not global.skip_intro then
    if game.is_multiplayer() then
      player.print({"msg-intro"})
    else
      game.show_message_dialog{text = {"msg-intro"}}
    end
  end

  silo_script.on_event(event)
end)

script.on_event(defines.events.on_player_respawned, function(event)
  local player = game.players[event.player_index]
  util.insert_safe(player, global.respawn_items)
  silo_script.on_event(event)
end)

script.on_configuration_changed(function(event)
  global.created_items = global.created_items or created_items()
  global.respawn_items = global.respawn_items or respawn_items()
  silo_script.on_configuration_changed(event)
end)

script.on_load(function()
  silo_script.on_load()
end)

script.on_init(function()
  global.created_items = created_items()
  global.respawn_items = respawn_items()
  silo_script.on_init()

  -- fadmin --
  global.events = {}
end)

silo_script.add_remote_interface()
silo_script.add_commands()

remote.add_interface("freeplay",
{
  get_created_items = function()
    return global.created_items
  end,
  set_created_items = function(map)
    global.created_items = map
  end,
  get_respawn_items = function()
    return global.respawn_items
  end,
  set_respawn_items = function(map)
    global.respawn_items = map
  end,
  set_skip_intro = function(bool)
    global.skip_intro = bool
  end,
  set_chart_distance = function(value)
    global.chart_distance = tonumber(value)
  end
})


-- fadmin --

local json = require('json')

script.on_event(defines.events.on_console_chat, function(event)
  local name
  if event.player_index == nil then
    name = '<server>'
  else
    name = game.players[event.player_index].name
  end
  table.insert(global.events, {
    type = 'chat',
    name = name,
    message = event.message
  })
end)

script.on_event(defines.events.on_player_joined_game, function(event)
  table.insert(global.events, {
    type = 'joined',
    name = game.players[event.player_index].name
  })
end)

script.on_event(defines.events.on_player_left_game, function(event)
  table.insert(global.events, {
    type = 'left',
    name = game.players[event.player_index].name
  })
end)

script.on_event(defines.events.on_player_died, function(event)
  local cause = nil
  if event.cause ~= nil then
    cause = {type = event.cause.name, player = nil}
    if event.cause.type == 'player' and event.cause.player ~= nil then
      cause['player'] = event.cause.player.name
    end
  end
  table.insert(global.events, {
    type = 'died',
    name = game.players[event.player_index].name,
    cause = cause
  })
end)

remote.add_interface('fadmin', {
  poll = function()
    rcon.print(json.encode(global.events))
    global.events = {}
  end,
})

script.on_event(defines.events.on_chunk_generated, function(event)
  event.surface.destroy_decoratives({area=event.area})
end)
