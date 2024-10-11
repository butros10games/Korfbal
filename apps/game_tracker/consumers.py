from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.db.models import Q, Case, When

from apps.game_tracker.models import GoalType, PlayerChange, Pause, PlayerGroup, GroupTypes, Shot, MatchPart
from apps.player.models import Player
from apps.schedule.models import Match, Season
from apps.team.models import Team, TeamData

import json
import traceback
from datetime import datetime

from django.utils.timezone import make_aware
            
class match_data(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.match = None
        self.current_part = None
        self.user_id = None
        
    async def connect(self):
        match_id = self.scope['url_route']['kwargs']['id']
        self.match = await sync_to_async(Match.objects.prefetch_related('home_team','away_team').get)(id_uuid=match_id)
        
        try:
            self.current_part = await sync_to_async(MatchPart.objects.get)(match=self.match, active=True)
        except MatchPart.DoesNotExist:
            pass
        
        self.channel_names = ['detail_match_%s' % self.match.id_uuid, 'tracker_match_%s' % self.match.id_uuid, 'time_match_%s' % self.match.id_uuid]
        for channel_name in [self.channel_names[0], self.channel_names[2]]:
            await self.channel_layer.group_add(channel_name, self.channel_name)
        
        await self.accept()
        
    async def disconnect(self, close_code):
        for channel_name in self.channel_names:
            await self.channel_layer.group_discard(channel_name, self.channel_name)
    
    async def receive(self, text_data):
        try:
            json_data = json.loads(text_data)
            command = json_data['command']
            
            if command == "match_events":
                self.user_id = json_data['user_id']
                await self.get_events()
                
            elif command == "get_time":
                await get_time(self)
            
            elif command == "home_team":
                self.user_id = json_data['user_id']
                team = self.match.home_team
                
                player_groups_array = await self.makePlayerGroupList(team)
                
                players_json = await self.makePlayerList(team)
                
                await self.send(text_data=json.dumps({
                    'command': 'playerGroups',
                    'playerGroups': player_groups_array,
                    'players': players_json,
                    'is_coach': await self.checkIfAcces(self.user_id, team),
                    'finished': self.match.finished
                }))
                
            elif command == "away_team":
                self.user_id = json_data['user_id']
                team = self.match.away_team
                
                player_groups_array = await self.makePlayerGroupList(team)
                
                players_json = await self.makePlayerList(team)
                
                await self.send(text_data=json.dumps({
                    'command': 'playerGroups',
                    'playerGroups': player_groups_array,
                    'players': players_json,
                    'is_coach': await self.checkIfAcces(self.user_id, team),
                    'finished': self.match.finished
                }))
            
            elif command == "follow":
                follow = json_data['followed']
                self.user_id = json_data['user_id']
                
                player = await sync_to_async(TeamData.objects.get)(user=self.user_id)
                
                if follow:
                    await sync_to_async(player.club_follow.add)(self.club)
                    
                else:
                    await sync_to_async(player.club_follow.remove)(self.club)
                
                await self.send(text_data=json.dumps({
                    'command': 'follow',
                    'status': 'success'
                }))
                
            elif command == "savePlayerGroups":
                player_groups = json_data['playerGroups']
                
                for player_group in player_groups:
                    group = await sync_to_async(PlayerGroup.objects.get)(id_uuid=player_group['id'])
                    await sync_to_async(group.players.clear)()
                    
                    for player in player_group['players']:
                        if player == 'NaN':
                            continue
                        player_obj = await sync_to_async(Player.objects.get)(id_uuid=player)
                        await sync_to_async(group.players.add)(player_obj)
                        
                    await sync_to_async(group.save)()
                
                await self.send(text_data=json.dumps({
                    'command': 'savePlayerGroups',
                    'status': 'success'
                }))
                
            elif command == "get_stats":
                data_type = json_data['data_type']
                
                if data_type == 'general':
                    ## get the amount of goals for and against for all the types
                    goal_types = await sync_to_async(list)(GoalType.objects.all())
                    
                    goal_types_json = [
                        {
                            'id': str(goal_type.id_uuid),
                            'name': goal_type.name
                        }
                        for goal_type in goal_types
                    ]
                    
                    team_goal_stats = {}
                    for goal_type in goal_types:
                        goals_for = await sync_to_async(Shot.objects.filter(match=self.match, shot_type=goal_type, for_team=True, scored=True).count)()
                        goals_against = await sync_to_async(Shot.objects.filter(match=self.match, shot_type=goal_type, for_team=False, scored=True).count)()
                        
                        team_goal_stats[goal_type.name] = {
                            "goals_by_player": goals_for,
                            "goals_against_player": goals_against
                        }
                    
                    await self.send(text_data=json.dumps({
                        'command': 'stats',
                        'data': {
                            'type': 'general',
                            'stats': {
                                'shots_for': await sync_to_async(Shot.objects.filter(match=self.match, for_team=True).count)(),
                                'shots_against': await sync_to_async(Shot.objects.filter(match=self.match, for_team=False).count)(),
                                'goals_for': await sync_to_async(Shot.objects.filter(match=self.match, for_team=True, scored=True).count)(),
                                'goals_against': await sync_to_async(Shot.objects.filter(match=self.match, for_team=False, scored=True).count)(),
                                'team_goal_stats': team_goal_stats,
                                'goal_types': goal_types_json,
                            }
                        }
                    }))
                
                elif data_type == 'player_stats':
                    ## Get the player stats. shots for and against, goals for and against.
                    players = await sync_to_async(list)(Player.objects.prefetch_related('user').filter(Q(team_data_as_player__team=self.match.home_team) | Q(team_data_as_player__team=self.match.away_team)).distinct())
                    
                    players_stats = []
                    for player in players:
                        player_stats = {
                            'username': player.user.username,
                            'shots_for': await sync_to_async(Shot.objects.filter(match=self.match, player=player, for_team=True).count)(),
                            'shots_against': await sync_to_async(Shot.objects.filter(match=self.match, player=player, for_team=False).count)(),
                            'goals_for': await sync_to_async(Shot.objects.filter(match=self.match, player=player, for_team=True, scored=True).count)(),
                            'goals_against': await sync_to_async(Shot.objects.filter(match=self.match, player=player, for_team=False, scored=True).count)(),
                        }
                        
                        players_stats.append(player_stats)
                        
                    ## sort the `player_stats` so the player with the most goals for is on top
                    players_stats = sorted(players_stats, key=lambda x: x['goals_for'], reverse=True)
                        
                    await self.send(text_data=json.dumps({
                        'command': 'stats',
                        'data': {
                            'type': 'player_stats',
                            'stats': {
                                'player_stats': players_stats
                            }
                        }
                    }))
                    
            
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            }))
            
    async def get_events(self, event=None):
        try:
            try:
                part = await sync_to_async(MatchPart.objects.get)(match=self.match, active=True)
            except MatchPart.DoesNotExist:
                part = None
                
            events_dict = []
            
            # check if there is a part active or the match is finished
            if part != None or self.match.finished:
                goals = await sync_to_async(list)(Shot.objects.prefetch_related('player__user', 'shot_type', 'match_part').filter(match=self.match, scored=True).order_by('time'))
                player_change = await sync_to_async(list)(PlayerChange.objects.prefetch_related('player_in', 'player_out__user', 'player_group', 'match_part').filter(player_group__match=self.match).order_by('time'))
                time_outs = await sync_to_async(list)(Pause.objects.prefetch_related('match_part').filter(match=self.match).order_by('time'))
                
                # add all the events to a list and order them on time
                events = []
                events.extend(goals)
                events.extend(player_change)
                events.extend(time_outs)
                events.sort(key=lambda x: x.time)
                
                for event in events:
                    if event.match_part is not None:
                        if isinstance(event, Shot):
                            # calculate the time of the pauses before the event happend. By requesting the pauses that are before the event and summing the length of the pauses
                            pauses = await sync_to_async(list)(Pause.objects.filter(match=self.match, active=False, time__lt=event.time, time__gte=event.match_part.start_time))
                            pause_time = 0
                            for pause in pauses:
                                pause_time += pause.length
                            
                            time_in_minutes = round(((event.time - event.match_part.start_time).total_seconds() + (int(event.match_part.part_number - 1) * int(self.match.part_lenght)) - pause_time) / 60)
                            
                            left_over = time_in_minutes - ((event.match_part.part_number * self.match.part_lenght) / 60)
                            if left_over > 0:
                                time_in_minutes = str(time_in_minutes - left_over).split(".")[0] + "+" + str(left_over).split(".")[0]
                            
                            events_dict.append({
                                'type': 'goal',
                                'time': time_in_minutes,
                                'player': event.player.user.username,
                                'goal_type': event.shot_type.name,
                                'for_team': event.for_team
                            })
                        elif isinstance(event, PlayerChange):
                            # calculate the time of the pauses before the event happend. By requesting the pauses that are before the event and summing the length of the pauses
                            pauses = await sync_to_async(list)(Pause.objects.filter(match=self.match, active=False, time__lt=event.time, time__gte=event.match_part.start_time))
                            pause_time = 0
                            for pause in pauses:
                                pause_time += pause.length
                                
                            time_in_minutes = round(((event.time - event.match_part.start_time).total_seconds() + ((event.match_part.part_number - 1) * self.match.part_lenght) - pause_time) / 60)
                            
                            left_over = time_in_minutes - ((event.match_part.part_number * self.match.part_lenght) / 60)
                            if left_over > 0:
                                time_in_minutes = str(time_in_minutes - left_over).split(".")[0] + "+" + str(left_over).split(".")[0]
                            
                            async def get_username(player):
                                user = await sync_to_async(lambda: player.user)()
                                return user.username
                            
                            player_in_username = await get_username(event.player_in)
                            player_out_username = await get_username(event.player_out)
                            
                            events_dict.append({
                                'type': 'wissel',
                                'time': time_in_minutes,
                                'player_in': player_in_username,
                                'player_out': player_out_username,
                                'player_group': str(event.player_group.id_uuid)
                            })
                        elif isinstance(event, Pause):
                            # calculate the time of the pauses before the event happend. By requesting the pauses that are before the event and summing the length of the pauses
                            pauses = await sync_to_async(list)(Pause.objects.filter(match=self.match, active=False, time__lt=event.time, time__gte=event.match_part.start_time))
                            pause_time = 0
                            for pause in pauses:
                                pause_time += pause.length
                                
                            # calculate the time in minutes sinds the real_start_time of the match and the start_time of the pause
                            time_in_minutes = round(((event.time - event.match_part.start_time).total_seconds() + (int(event.match_part.part_number - 1) * int(self.match.part_lenght)) - pause_time) / 60)
                            
                            left_over = time_in_minutes - ((event.match_part.part_number * self.match.part_lenght) / 60)
                            if left_over > 0:
                                time_in_minutes = str(time_in_minutes - left_over).split(".")[0] + "+" + str(left_over).split(".")[0]
                            
                            events_dict.append({
                                'type': 'pauze',
                                'time': time_in_minutes,
                                'length': event.length,
                                'start_time': event.time.isoformat() if event.time else None,
                                'end_time': event.end_time.isoformat() if event.end_time else None
                            })
            
            ## Check if player is in the home or away team
            player = await sync_to_async(Player.objects.get)(user=self.user_id)
            
            players_home = await sync_to_async(list)(TeamData.objects.prefetch_related('players').filter(team=self.match.home_team).values_list('players', flat=True))
            coaches_home = await sync_to_async(list)(TeamData.objects.prefetch_related('coach').filter(team=self.match.home_team).values_list('coach', flat=True))

            players_away = await sync_to_async(list)(TeamData.objects.prefetch_related('players').filter(team=self.match.away_team).values_list('players', flat=True))
            coaches_away = await sync_to_async(list)(TeamData.objects.prefetch_related('coach').filter(team=self.match.away_team).values_list('coach', flat=True))
            
            players_list = []
            
            players_list.extend(players_home)
            players_list.extend(coaches_home)
            players_list.extend(players_away)
            players_list.extend(coaches_away)
            
            access = False
            if player.id_uuid in players_list:
                access = True
            
            await self.send(text_data=json.dumps({
                'command': 'events',
                'events': events_dict,
                'access': access,
                'finished': self.match.finished
            }))
        
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            }))
            
    async def makePlayerGroupList(self, team):
        try:
            player_groups = await sync_to_async(list)(PlayerGroup.objects.prefetch_related('players', 'players__user', 'starting_type', 'current_type').filter(match=self.match, team=team).order_by('starting_type'))
            
            # When there is no connected player group create the player groups
            if player_groups == []:
                group_types = await sync_to_async(list)(GroupTypes.objects.all())
                
                for group_type in group_types:
                    await sync_to_async(PlayerGroup.objects.create)(match=self.match, team=team, starting_type=group_type, current_type=group_type)
                    
                player_groups = await sync_to_async(list)(PlayerGroup.objects.prefetch_related('players', 'players__user', 'starting_type', 'current_type').filter(match=self.match, team=team).order_by('starting_type'))
            
            # make it a json parsable string
            player_groups_array = [
                {
                    'id': str(player_group.id_uuid),
                    'players': [
                        {
                            'id': str(player.id_uuid),
                            'name': player.user.username,
                        }
                        for player in player_group.players.all()
                    ],
                    'starting_type': player_group.starting_type.name,
                    'current_type': player_group.current_type.name
                }
                for player_group in player_groups
            ]
            
            return player_groups_array
        
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc(),
                'player_groups': player_groups
            }))
            
    async def makePlayerList(self, team):
        # get the season of the match
        season = await self.season_request()
            
        players_json = []
        players = await sync_to_async(list)(TeamData.objects.prefetch_related('players').filter(team=team, season=season).values_list('players', flat=True))
        
        for player in players:
            try:
                player_json = await sync_to_async(Player.objects.prefetch_related('user').get)(id_uuid=player)
                players_json.append({
                    'id': str(player_json.id_uuid),
                    'name': player_json.user.username,
                    'profile_picture': player_json.profile_picture.url if player_json.profile_picture else None,
                    'get_absolute_url': str(player_json.get_absolute_url())
                })
            except Player.DoesNotExist:
                pass
        
        # remove duplicates
        players_json = [dict(t) for t in {tuple(d.items()) for d in players_json}]
        
        return players_json
    
    async def checkIfAcces(self, user_id, team):
        player = await sync_to_async(Player.objects.get)(user=user_id)
        
        players = await sync_to_async(list)(TeamData.objects.prefetch_related('players').filter(team=team).values_list('players', flat=True))
        coaches = await sync_to_async(list)(TeamData.objects.prefetch_related('coach').filter(team=team).values_list('coach', flat=True))

        
        players_list = []
        
        players_list.extend(players)
        players_list.extend(coaches)
        
        access = False
        if player.id_uuid in players_list:
            access = True
            
        return access
    
    async def send_data(self, event):
        data = event['data']
        await self.send(text_data=json.dumps(data))
        
    async def season_request(self):
        try:
            return await sync_to_async(Season.objects.get)(start_date__lte=self.match.start_time, end_date__gte=self.match.start_time)
        except Season.DoesNotExist:
            return await sync_to_async(Season.objects.filter(end_date__lte=self.match.start_time).order_by('-end_date').first)()
    
class match_tracker(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.match = None
        self.current_part = None
        self.is_paused = False
        
    async def connect(self):
        match_id = self.scope['url_route']['kwargs']['id']
        self.match = await sync_to_async(Match.objects.prefetch_related('home_team','away_team').get)(id_uuid=match_id)
        self.team = await sync_to_async(Team.objects.get)(id_uuid=self.scope['url_route']['kwargs']['team_id'])
        try:
            self.current_part = await sync_to_async(MatchPart.objects.get)(match=self.match, active=True)
        except MatchPart.DoesNotExist:
            pass
            
        try:
            pause = await sync_to_async(Pause.objects.get)(match=self.match, active=True) 
            self.is_paused = True
        except Pause.DoesNotExist:
            ## if match is not active the game is also paused
            if not self.match.active:
                self.is_paused = True
            
            pass
        
        if self.team == self.match.home_team:
            self.other_team = self.match.away_team
        else:
            self.other_team = self.match.home_team
        
        self.channel_names = ['detail_match_%s' % self.match.id_uuid, 'tracker_match_%s' % self.match.id_uuid, 'time_match_%s' % self.match.id_uuid]
        for channel_name in [self.channel_names[1], self.channel_names[2]]:
            await self.channel_layer.group_add(channel_name, self.channel_name)
        
        await self.accept()
        
        if self.match.finished:
            await self.send(text_data=json.dumps({
                'command': 'match_end',
                'match_id': str(self.match.id_uuid)
            }))
        
    async def disconnect(self, close_code):
        pass
    
    async def receive(self, text_data):
        try:
            json_data = json.loads(text_data)
            command = json_data['command']
            
            if command == "playerGroups":
                await self.playerGroupRequest()
                
            elif command == "savePlayerGroups":
                player_groups = json_data['playerGroups']
                
                for player_group in player_groups:
                    group = await sync_to_async(PlayerGroup.objects.get)(id_uuid=player_group['id'])
                    await sync_to_async(group.players.clear)()
                    
                    for player in player_group['players']:
                        if player == 'NaN':
                            continue
                        player_obj = await sync_to_async(Player.objects.get)(id_uuid=player)
                        await sync_to_async(group.players.add)(player_obj)
                        
                    await sync_to_async(group.save)()
                
                await self.send(text_data=json.dumps({
                    'command': 'savePlayerGroups',
                    'status': 'success'
                }))
                
            elif command == "shot_reg":
                # check if the match is paused and if it is paused decline the request except for the start/stop command
                if self.is_paused:
                    await self.send(text_data=json.dumps({
                        'error': 'match is paused'
                    }))
                    return
            
                await sync_to_async(Shot.objects.create)(player=await sync_to_async(Player.objects.get)(id_uuid=json_data['player_id']), match=self.match, match_part = self.current_part, time = json_data['time'], for_team=json_data['for_team'])
                
                await self.channel_layer.group_send(self.channel_names[1], {
                    'type': 'send_data',
                    'data': {
                        'command': 'player_shot_change',
                        'player_id': json_data['player_id'],
                        'shots_for': await sync_to_async(Shot.objects.filter(player__id_uuid=json_data['player_id'], match=self.match, for_team = True).count)(),
                        'shots_against': await sync_to_async(Shot.objects.filter(player__id_uuid=json_data['player_id'], match=self.match, for_team = False).count)()
                    }
                })
                
                await self.get_last_event()
                
            elif command == "get_goal_types":
                goal_type_list = await sync_to_async(list)(GoalType.objects.all())
                
                goal_type_list = [
                    {
                        'id': str(goal_type.id_uuid),
                        'name': goal_type.name
                    }
                    for goal_type in goal_type_list
                ]
                
                await self.send(text_data=json.dumps({
                    'command': 'goal_types',
                    'goal_types': goal_type_list
                }))
                
            elif command == "goal_reg":
                # check if the match is paused and if it is paused decline the request except for the start/stop command
                if self.is_paused:
                    await self.send(text_data=json.dumps({
                        'error': 'match is paused'
                    }))
                    return
                
                if json_data['for_team']:
                    team = self.team
                else:
                    team = self.other_team
                
                await sync_to_async(Shot.objects.create)(player=await sync_to_async(Player.objects.get)(id_uuid=json_data['player_id']), match=self.match, match_part = self.current_part, time = json_data['time'], shot_type=await sync_to_async(GoalType.objects.get)(id_uuid=json_data['goal_type']), for_team=json_data['for_team'], team=team, scored=True)
                
                for channel_name in [self.channel_names[1], self.channel_names[0]]:
                    await self.channel_layer.group_send(channel_name, {
                        'type': 'send_data',
                        'data': {
                            'command': 'player_shot_change',
                            'player_id': json_data['player_id'],
                            'shots_for': await sync_to_async(Shot.objects.filter(player__id_uuid=json_data['player_id'], match=self.match, for_team = True).count)(),
                            'shots_against': await sync_to_async(Shot.objects.filter(player__id_uuid=json_data['player_id'], match=self.match, for_team = False).count)()
                        }
                    })
                
                player = await sync_to_async(Player.objects.prefetch_related('user').get)(id_uuid=json_data['player_id'])
                goal_type = await sync_to_async(GoalType.objects.get)(id_uuid=json_data['goal_type'])
                
                for channel_name in [self.channel_names[1], self.channel_names[0]]:
                    await self.channel_layer.group_send(channel_name, {
                        'type': 'send_data',
                        'data': {
                            'command': 'team_goal_change',
                            'player_name': player.user.username,
                            'goal_type': goal_type.name,
                            'goals_for': await sync_to_async(Shot.objects.filter(match=self.match, team=self.team, scored=True).count)(),
                            'goals_against': await sync_to_async(Shot.objects.filter(match=self.match, team=self.other_team, scored=True).count)()
                        }
                    })
                
                if (await sync_to_async(Shot.objects.filter(match=self.match, scored=True).count)()) % 2 == 0:
                    await self.swap_player_group_types(self.team)
                    await self.swap_player_group_types(self.other_team)
                    
                    await self.playerGroupRequest()
                        
                await self.get_last_event()
                
                await self.channel_layer.group_send(self.channel_names[0], {
                    'type': 'get_events'
                })
                    
            elif command == "start/pause":
                try:
                    part = await sync_to_async(MatchPart.objects.get)(match=self.match, active=True)
                except MatchPart.DoesNotExist:
                    part = await sync_to_async(MatchPart.objects.create)(match=self.match, active=True, start_time=datetime.now(), part_number=self.match.current_part)
                    
                    # reload part from database
                    part = await sync_to_async(MatchPart.objects.get)(match=self.match, active=True)
                    
                    self.current_part = part
                    
                    self.is_paused = False
                    
                    if self.match.current_part == 1:
                        self.match.active = True
                        await sync_to_async(self.match.save)()
                        
                        await self.playerGroupRequest()
                    
                    for channel_name in [self.channel_names[2]]:
                        await self.channel_layer.group_send(channel_name, {
                            'type': 'send_data',
                            'data': {
                                'command': 'timer_data',
                                'type': 'start',
                                'time': part.start_time.isoformat(),
                                'length': self.match.part_lenght
                            }
                        })
                else:
                    try:
                        pause = await sync_to_async(Pause.objects.get)(match=self.match, active=True, match_part = self.current_part)
                    except Pause.DoesNotExist:
                        pause = await sync_to_async(Pause.objects.create)(match=self.match, active=True, time=datetime.now(), match_part = self.current_part)
                        
                        self.is_paused = True
                        pause_message = {'command': 'pause', 'pause': True}
                    else:
                        naive_datetime = datetime.now()
                        aware_datetime = make_aware(naive_datetime)
                        pause.active = False
                        pause.end_time = aware_datetime
                        pause.length = (aware_datetime - pause.time).total_seconds()
                        await sync_to_async(pause.save)()
                        
                        self.is_paused = False
                        
                        pauses = await sync_to_async(list)(Pause.objects.filter(match=self.match, active=False, match_part = self.current_part))
                        pause_time = 0
                        for pause in pauses:
                            pause_time += pause.length
                        
                        pause_message = {'command': 'pause', 'pause': False, 'pause_time': pause_time}
                    
                    for channel_name in [self.channel_names[2]]:
                        await self.channel_layer.group_send(channel_name, {
                            'type': 'send_data',
                            'data': pause_message
                        })
                
                await self.get_last_event()
                
                await self.channel_layer.group_send(self.channel_names[0], {
                    'type': 'get_events'
                })
                    
            elif command == "part_end":
                try:
                    pause = await sync_to_async(Pause.objects.get)(match=self.match, active=True, match_part = self.current_part)
                    
                    naive_datetime = datetime.now()
                    aware_datetime = make_aware(naive_datetime)
                    pause.active = False
                    pause.end_time = aware_datetime
                    pause.length = (aware_datetime - pause.time).total_seconds()
                    await sync_to_async(pause.save)()
                    
                except Pause.DoesNotExist:
                    pass
                
                if self.match.current_part < self.match.parts:
                    self.match.current_part += 1
                    await sync_to_async(self.match.save)()
                    
                    try:
                        match_part = await sync_to_async(MatchPart.objects.get)(match=self.match, active=True)
                        match_part.active = False
                        match_part.end_time = datetime.now()
                        await sync_to_async(match_part.save)()
                        
                    except MatchPart.DoesNotExist:
                        pass
                    
                    for channel_name in [self.channel_names[2]]:
                        await self.channel_layer.group_send(channel_name, {
                            'type': 'send_data',
                            'data': {
                                'command': 'part_end',
                                'part': self.match.current_part,
                                'part_length': self.match.part_lenght
                            }
                        })
                    
                else:
                    self.match.finished = True
                    self.match.active = False
                    await sync_to_async(self.match.save)()
                    
                    match_part = await sync_to_async(MatchPart.objects.get)(match=self.match, active=True)
                    match_part.active = False
                    match_part.end_time = datetime.now()
                    await sync_to_async(match_part.save)()
                    
                    for channel_name in [self.channel_names[2]]:
                        await self.channel_layer.group_send(channel_name, {
                            'type': 'send_data',
                            'data': {
                                'command': 'match_end',
                                'match_id': str(self.match.id_uuid)
                            }
                        })
                    
            elif command == "get_time":
                await get_time(self)
                    
            elif command == "last_event":
                await self.get_last_event()
                
            elif command == "get_non_active_players":
                # Get all player groups for the team and remove the players that are already in a group
                player_groups = await self.get_player_groups(self.team)
                grouped_players = [player for group in player_groups for player in group.players.all()]
                
                season = await self.season_request()
                
                # Get all players for the team, excluding those that are already in a group
                team_data_list = await sync_to_async(list)(TeamData.objects.prefetch_related('players', 'players__user').filter(team=self.team, season=season))

                # Get all players for each TeamData object, excluding those that are already in a group
                all_players = [player for team_data in team_data_list for player in team_data.players.all()]
                
                ## romove the players that are already in a group
                non_play_players = [player for player in all_players if player not in grouped_players]
                
                players_json = []
                for player in non_play_players:
                    try:
                        players_json.append({
                            'id': str(player.id_uuid),
                            'name': player.user.username
                        })
                    except Player.DoesNotExist:
                        pass
                    
                await self.send(text_data=json.dumps({
                    'command': 'non_active_players',
                    'players': players_json
                }))
            
            elif command == "wissel_reg":
                # check if the match is paused and if it is paused decline the request except for the start/stop command
                if self.is_paused:
                    await self.send(text_data=json.dumps({
                        'error': 'match is paused'
                    }))
                    return
                
                player_in = await sync_to_async(Player.objects.prefetch_related('user').get)(id_uuid=json_data['new_player_id'])
                player_out = await sync_to_async(Player.objects.prefetch_related('user').get)(id_uuid=json_data['old_player_id'])
                player_group = await sync_to_async(PlayerGroup.objects.get)(team=self.team, match=self.match, players__in=[player_out])
                
                await sync_to_async(player_group.players.remove)(player_out)
                await sync_to_async(player_group.players.add)(player_in)
                
                await sync_to_async(PlayerChange.objects.create)(player_in=player_in, player_out=player_out, player_group=player_group, match=self.match, match_part = self.current_part, time = json_data['time'])
                
                ## get the shot count for the new player
                shots_for = await sync_to_async(Shot.objects.filter(player=player_in, match=self.match, for_team = True).count)()
                shots_against = await sync_to_async(Shot.objects.filter(player=player_in, match=self.match, for_team = False).count)()
                
                for channel_name in [self.channel_names[1]]:
                    await self.channel_layer.group_send(channel_name, {
                        'type': 'send_data',
                        'data': {
                            'command': 'player_change',
                            'player_in': player_in.user.username,
                            'player_in_id': str(player_in.id_uuid),
                            'player_in_shots_for': shots_for,
                            'player_in_shots_against': shots_against,
                            'player_out': player_out.user.username,
                            'player_out_id': str(player_out.id_uuid),
                            'player_group': str(player_group.id_uuid)
                        }
                    })
                    
                await self.get_last_event()
                
                await self.channel_layer.group_send(self.channel_names[0], {
                    'type': 'get_events'
                })
            
            elif command == "remove_last_event":
                event = await self.get_last_event_element()
                
                if isinstance(event, Shot):
                    # get and delete the last shot event
                    shot = await sync_to_async(Shot.objects.prefetch_related('player', 'player__user', 'shot_type').get)(match_part = event.match_part, time = event.time)
                    
                    player_id = str(shot.player.id_uuid)
                    
                    await sync_to_async(shot.delete)()
                    
                    # send player shot update message
                    await self.channel_layer.group_send(self.channel_names[1], {
                        'type': 'send_data',
                        'data': {
                            'command': 'player_shot_change',
                            'player_id': player_id,
                            'shots_for': await sync_to_async(Shot.objects.filter(player__id_uuid=player_id, match=self.match, for_team = True).count)(),
                            'shots_against': await sync_to_async(Shot.objects.filter(player__id_uuid=player_id, match=self.match, for_team = False).count)()
                        }
                    })
                        
                    # check if the shot was a goal and if it was a goal check if it was a switch goal and if it was a switch goal swap the player group types back
                    if shot.scored:
                        for channel_name in [self.channel_names[1], self.channel_names[0]]:
                            await self.channel_layer.group_send(channel_name, {
                                'type': 'send_data',
                                'data': {
                                    'command': 'team_goal_change',
                                    'player_name': shot.player.user.username,
                                    'goal_type': shot.shot_type.name,
                                    'goals_for': await sync_to_async(Shot.objects.filter(match=self.match, team=self.team, scored=True).count)(),
                                    'goals_against': await sync_to_async(Shot.objects.filter(match=self.match, team=self.other_team, scored=True).count)()
                                }
                            })
                            
                        if (await sync_to_async(Shot.objects.filter(match=self.match, scored=True).count)()) % 2 == 1:
                            await self.swap_player_group_types(self.team)
                            await self.swap_player_group_types(self.other_team)
                            
                            await self.playerGroupRequest()
                            
                elif isinstance(event, PlayerChange):
                    # get and delete the last player change event
                    player_change = await sync_to_async(PlayerChange.objects.prefetch_related('player_group', 'player_in', 'player_out').get)(match_part = event.match_part, time = event.time)
                    player_group = await sync_to_async(PlayerGroup.objects.get)(id_uuid=player_change.player_group.id_uuid)
                    
                    await sync_to_async(player_group.players.remove)(player_change.player_in)
                    await sync_to_async(player_group.players.add)(player_change.player_out)
                    
                    await sync_to_async(player_group.save)()
                    
                    await sync_to_async(player_change.delete)()
                    
                    # send player group update message
                    await self.playerGroupRequest()
                    
                elif isinstance(event, Pause):
                    # get and delete the last pause event
                    pause = await sync_to_async(Pause.objects.get)(active=event.active, match_part = event.match_part, time = event.time)
                    
                    if event.active:
                        await sync_to_async(pause.delete)()
                    else:
                        pause.active = True
                        pause.end_time = None
                        pause.length = None
                        await sync_to_async(pause.save)()
                        
                    # send the timer message
                    await get_time(self)
                    
                await self.get_last_event()
                
                await self.channel_layer.group_send(self.channel_names[0], {
                    'type': 'get_events'
                })

        except Exception as e:
                await self.send(text_data=json.dumps({
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }))
                
    async def get_last_event_element(self):
        # Fetch each type of event separately
        shots = await sync_to_async(list)(Shot.objects.prefetch_related('player__user', 'match_part', 'shot_type').filter(match=self.match).order_by('time'))
        player_changes = await sync_to_async(list)(PlayerChange.objects.prefetch_related('player_in', 'player_in__user', 'player_out', 'player_out__user', 'player_group', 'match_part').filter(player_group__match=self.match).order_by('time'))
        time_outs = await sync_to_async(list)(Pause.objects.prefetch_related('match_part').filter(match=self.match).order_by('time'))

        # Combine all events and sort them
        events = sorted(shots + player_changes + time_outs, key=lambda x: x.time)
        
        # check if there are events
        if events == []:
            await self.send(text_data=json.dumps({
                'command': 'last_event',
                'last_event': {
                    'type': 'no_event'
                }
            }))
            return None
        
        # Get last event
        return events[-1]
                
    async def get_last_event(self):
        last_event = await self.get_last_event_element()
        
        if last_event == None:
            return
        
        if isinstance(last_event, Shot):
            time_in_minutes = await self.time_calc(last_event)
            
            if last_event.scored == False:
                events_dict = ({
                    'type': 'shot',
                    'time': time_in_minutes,
                    'player': last_event.player.user.username,
                    'for_team': last_event.for_team
                })
            else:
                events_dict = ({
                    'type': 'goal',
                    'time': time_in_minutes,
                    'player': last_event.player.user.username,
                    'goal_type': last_event.shot_type.name,
                    'for_team': last_event.for_team,
                    'goals_for': await sync_to_async(Shot.objects.filter(match=self.match, for_team=True, scored=True).count)(),
                    'goals_against': await sync_to_async(Shot.objects.filter(match=self.match, for_team=False, scored=True).count)()
                })
        elif isinstance(last_event, PlayerChange):
            player_in_username = last_event.player_in.user.username
            player_out_username = last_event.player_out.user.username
            
            time_in_minutes = await self.time_calc(last_event)

            events_dict = ({
                'type': 'wissel',
                'time': time_in_minutes,
                'player_in': player_in_username,
                'player_out': player_out_username,
                'player_group': str(last_event.player_group.id_uuid)
            })
        elif isinstance(last_event, Pause):
            time_in_minutes = await self.time_calc(last_event)
            
            events_dict = ({
                'type': 'pause',
                'time': time_in_minutes,
                'length': last_event.length,
                'start_time': last_event.time.isoformat() if last_event.time else None,
                'end_time': last_event.end_time.isoformat() if last_event.end_time else None
            })
        
        await self.send(text_data=json.dumps({
            "command": "last_event",
            "last_event": events_dict
        }))
        
    async def time_calc(self, event):
        # calculate the time of the pauses before the event happend. By requesting the pauses that are before the event and summing the length of the pauses
        pauses = await sync_to_async(list)(Pause.objects.filter(match=self.match, active=False, time__lt=event.time, time__gte=event.match_part.start_time))
        pause_time = 0
        for pause in pauses:
            pause_time += pause.length
            
        # calculate the time in minutes sinds the real_start_time of the match and the start_time of the pause
        time_in_minutes = round(((event.time - event.match_part.start_time).total_seconds() + (int(event.match_part.part_number - 1) * int(self.match.part_lenght)) - pause_time) / 60)
        
        left_over = time_in_minutes - ((event.match_part.part_number * self.match.part_lenght) / 60)
        if left_over > 0:
            time_in_minutes = str(time_in_minutes - left_over).split(".")[0] + "+" + str(left_over).split(".")[0]
            
        return time_in_minutes
                
    async def playerGroupRequest(self):
        team = self.team
                
        player_groups_array = await self.makePlayerGroupList(team)
        players_json = await self.makePlayerList(team)
        
        await self.send(text_data=json.dumps({
            'command': 'playerGroups',
            'playerGroups': player_groups_array,
            'players': players_json,
            'full_player_list': await self.makeFullPlayerList(self.team),
            'match_active': self.match.active
        }))            
                
    async def create_player_groups(self, team):
        group_types = await sync_to_async(list)(GroupTypes.objects.all().order_by('id'))
        for group_type in group_types:
            await sync_to_async(PlayerGroup.objects.create)(match=self.match, team=team, starting_type=group_type, current_type=group_type)

    async def get_player_groups(self, team):
        return await sync_to_async(list)(
            PlayerGroup.objects.prefetch_related('players', 'players__user', 'starting_type', 'current_type')
            .filter(match=self.match, team=team)
            .order_by(Case(When(current_type__name='Aanval', then=0), default=1), 'starting_type')
        )

    async def make_player_group_json(self, player_groups):
        async def process_player(player):
            return {
                'id': str(player.id_uuid),
                'name': player.user.username,
                'shots_for': await sync_to_async(Shot.objects.filter(player=player, match=self.match, for_team = True).count)(),
                'shots_against': await sync_to_async(Shot.objects.filter(player=player, match=self.match, for_team = False).count)()
            }

        async def process_player_group(player_group):
            return {
                'id': str(player_group.id_uuid),
                'players': [await process_player(player) for player in player_group.players.all()],
                'starting_type': player_group.starting_type.name,
                'current_type': player_group.current_type.name
            }

        return [await process_player_group(player_group) for player_group in player_groups]

    async def makePlayerGroupList(self, team):
        player_groups = await self.get_player_groups(team)
        if not player_groups:
            await self.create_player_groups(team)
            player_groups = await self.get_player_groups(team)
        return await self.make_player_group_json(player_groups)
            
    async def makePlayerList(self, team):
        players_json = []
        
        # Get all player groups for the team
        player_groups = await self.get_player_groups(team)
        
        # Get all players that are already in a group
        grouped_players = [player for group in player_groups for player in group.players.all()]
        
        # Get all players for the team, excluding those that are already in a group
        players = await sync_to_async(list)(TeamData.objects.prefetch_related('players').filter(team=team).exclude(players__in=grouped_players).values_list('players', flat=True))
        
        for player in players:
            try:
                player_json = await sync_to_async(Player.objects.prefetch_related('user').get)(id_uuid=player)
                players_json.append({
                    'id': str(player_json.id_uuid),
                    'name': player_json.user.username,
                    'profile_picture': player_json.profile_picture.url if player_json.profile_picture else None,
                    'get_absolute_url': str(player_json.get_absolute_url())
                })
            except Player.DoesNotExist:
                pass
            
        # remove duplicates
        players_json = [dict(t) for t in {tuple(d.items()) for d in players_json}]
                    
        return players_json
    
    async def makeFullPlayerList(self, team):
        # get the season of the match
        season = await self.season_request()
            
        players_json = []
        players = await sync_to_async(list)(TeamData.objects.prefetch_related('players').filter(team=team, season=season).values_list('players', flat=True))
        
        for player in players:
            try:
                player_json = await sync_to_async(Player.objects.prefetch_related('user').get)(id_uuid=player)
                players_json.append({
                    'id': str(player_json.id_uuid),
                    'name': player_json.user.username,
                    'profile_picture': player_json.profile_picture.url if player_json.profile_picture else None,
                    'get_absolute_url': str(player_json.get_absolute_url())
                })
            except Player.DoesNotExist:
                pass
        
        # remove duplicates
        players_json = [dict(t) for t in {tuple(d.items()) for d in players_json}]
        
        return players_json
    
    async def swap_player_group_types(self, team):
        group_type_a = await sync_to_async(GroupTypes.objects.get)(name='Aanval')
        group_type_v = await sync_to_async(GroupTypes.objects.get)(name='Verdediging')

        player_group_a = await sync_to_async(PlayerGroup.objects.get)(match=self.match, team=team, current_type=group_type_a)
        player_group_v = await sync_to_async(PlayerGroup.objects.get)(match=self.match, team=team, current_type=group_type_v)

        player_group_a.current_type = group_type_v
        player_group_v.current_type = group_type_a

        await sync_to_async(player_group_a.save)()
        await sync_to_async(player_group_v.save)()
    
    async def send_data(self, event):
        data = event['data']
        await self.send(text_data=json.dumps(data))
        
    async def season_request(self):
        try:
            return await sync_to_async(Season.objects.get)(start_date__lte=self.match.start_time, end_date__gte=self.match.start_time)
        except Season.DoesNotExist:
            return await sync_to_async(Season.objects.filter(end_date__lte=self.match.start_time).order_by('-end_date').first)()

async def get_time(self):
    # check if there is a active part if there is a active part send the start time of the part and lenght of a match part
    try:
        part = await sync_to_async(MatchPart.objects.get)(match=self.match, active=True)
    except MatchPart.DoesNotExist:
        part = False
        
    if part:
        # check if there is a active pause if there is a active pause send the start time of the pause
        try:
            active_pause = await sync_to_async(Pause.objects.get)(match=self.match, active=True, match_part = self.current_part)
        except Pause.DoesNotExist:
            active_pause = False
        
        # calculate all the time in pauses that are not active anymore
        pauses = await sync_to_async(list)(Pause.objects.filter(match=self.match, active=False, match_part = self.current_part))
        pause_time = 0
        for pause in pauses:
            pause_time += pause.length
        
        if active_pause:
            await self.send(text_data=json.dumps({
                'command': 'timer_data',
                'type': 'pause',
                'time': part.start_time.isoformat(),
                'calc_to': active_pause.time.isoformat(),
                'length': self.match.part_lenght,
                'pause_length': pause_time
            }))
        else:
            await self.send(text_data=json.dumps({
                'command': 'timer_data',
                'type': 'active',
                'time': part.start_time.isoformat(),
                'length': self.match.part_lenght,
                'pause_length': pause_time
            }))
    else:
        await self.send(text_data=json.dumps({
            'command': 'timer_data',
            'type': 'deactive'
        }))