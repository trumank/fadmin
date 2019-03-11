json = require('json')

script.on_init(function()
  global.events = {}
end)

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
    if event.cause.player ~= nil then
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
