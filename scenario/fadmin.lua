on_console_chat = function(event)
  local name
  if event.player_index == nil then
    name = '<server>'
  else
    name = game.players[event.player_index].name

    -- message rate limiting
    local rate = 5
    local per  = 8 * 60
    if global.player_data[event.player_index] == nil then
      global.player_data[event.player_index] = {
        rl_allowance = rate,
        rl_last_check = event.tick
      }
    else
      local player = global.player_data[event.player_index];
      local time_passed = event.tick - player.rl_last_check
      player.rl_last_check = event.tick
      player.rl_allowance = player.rl_allowance + time_passed * (rate / per);
      if player.rl_allowance > rate then
        player.rl_allowance = rate
      end
      if player.rl_allowance < 1 then
        game.kick_player(game.players[event.player_index])
      else
        player.rl_allowance = player.rl_allowance - 1;
      end
    end
  end
  table.insert(global.events, {
    type = 'chat',
    name = name,
    message = event.message
  })
end

on_player_joined_game = function(event)
  table.insert(global.events, {
    type = 'joined',
    name = game.players[event.player_index].name
  })
end

on_player_left_game = function(event)
  table.insert(global.events, {
    type = 'left',
    name = game.players[event.player_index].name
  })
end

on_player_died = function(event)
  local cause = nil
  if event.cause ~= nil then
    cause = {type = event.cause.name, player = nil}
    if event.cause.type == 'character' and event.cause.player ~= nil then
      cause['player'] = event.cause.player.name
    end
  end
  table.insert(global.events, {
    type = 'died',
    name = game.players[event.player_index].name,
    cause = cause
  })
end

on_chunk_charted = function(event)
  if not global.spawned_tag then
    local surface = game.surfaces[event.surface_index]
    if surface.name == 'nauvis' and event.position.x == 0 and event.position.y == 0 then
      game.forces['player'].add_chart_tag(surface, {icon={type='virtual', name='signal-info'}, text='https://discord.gg/ZwMvyrs', position={0, 0}})
      global.spawned_tag = true
    end
  end
end

local fadmin = {}

fadmin.events =
{
  [defines.events.on_console_chat] = on_console_chat,
  [defines.events.on_player_joined_game] = on_player_joined_game,
  [defines.events.on_player_left_game] = on_player_left_game,
  [defines.events.on_player_died] = on_player_died,
  [defines.events.on_chunk_charted] = on_chunk_charted
}

fadmin.on_init = function()
  global.events = {}
  global.player_data = {}
  global.spawned_tag = false

  local default = game.permissions.get_group('Default')
  default.set_allows_action(defines.input_action.toggle_map_editor, false)

  local jail = game.permissions.create_group('Jail')
  for k, v in pairs(defines.input_action) do
    jail.set_allows_action(v, false)
  end
  jail.set_allows_action(defines.input_action.write_to_console, true)

  game.forces['player'].research_queue_enabled = true
end

fadmin.add_commands = function()
  commands.add_command('fadmin', 'FAdmin internal', function(event)
    if event.player_index == nil then
      parameter = event.parameter == nil and '' or event.parameter
      local res = string.match(parameter, 'poll')
      if res ~= nil then
        rcon.print(game.table_to_json(global.events))
        global.events = {}
      end
      res = string.match(parameter, 'chat (.*)')
      if res ~= nil then
          game.print(res, {.7,.7,.7})
          print(res)
      end
    end
  end)
end

return fadmin
