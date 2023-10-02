from channels.generic.websocket import AsyncWebsocketConsumer, WebsocketConsumer
from asgiref.sync import sync_to_async
from django.db.models import Q

from .models import Team, Match, Goal, GoalType, Season, TeamData, Player
from authentication.models import UserProfile
from django.core.files.base import ContentFile

import json
import traceback
import locale
from datetime import datetime
import base64

class team_data(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = None
    
    async def connect(self):
        team_id = self.scope['url_route']['kwargs']['id']
        self.team = await sync_to_async(Team.objects.get)(id_uuid=team_id)
        await self.accept()
        
    async def disconnect(self, close_code):
        pass
        
    async def receive(self, text_data):
        try:
            json_data = json.loads(text_data)
            command = json_data['command']
            
            if command == "wedstrijden":
                wedstrijden_data = await sync_to_async(list)(Match.objects.prefetch_related('home_team', 'away_team').filter(Q(home_team=self.team) | Q(away_team=self.team), finished=False).order_by('start_time'))
                
                wedstrijden_dict = await transfrom_matchdata(wedstrijden_data)
                
                await self.send(text_data=json.dumps({
                    'command': 'wedstrijden',
                    'wedstrijden': wedstrijden_dict
                }))
                
            elif command == "ended_matches":
                wedstrijden_data = await sync_to_async(list)(Match.objects.prefetch_related('home_team', 'away_team').filter(Q(home_team=self.team) | Q(away_team=self.team), finished=True).order_by('-start_time'))
                
                wedstrijden_dict = await transfrom_matchdata(wedstrijden_data)
                
                await self.send(text_data=json.dumps({
                    'command': 'wedstrijden',
                    'wedstrijden': wedstrijden_dict
                }))
                
            elif command == "team_stats":
                all_matches = await sync_to_async(Match.objects.filter)(Q(home_team=self.team, finished=True) | Q(away_team=self.team, finished=True))
                all_matches_list = await sync_to_async(list)(all_matches.prefetch_related('home_team', 'away_team'))
                
                goal_types = await sync_to_async(list)(GoalType.objects.all())

                goal_stats = {}
                scoring_types = []
                played_matches = await sync_to_async(all_matches.count)()
                total_goals_for = 0
                total_goals_against = 0
                
                for goal_type in goal_types:
                    goals_for = await sync_to_async(Goal.objects.filter(match__in=all_matches, goal_type=goal_type, for_team=True).count)()
                    goals_against = await sync_to_async(Goal.objects.filter(match__in=all_matches, goal_type=goal_type, for_team=False).count)()
            
                    goal_stats[goal_type.name] = {
                        "goals_for": goals_for,
                        "goals_against": goals_against
                    }
                    
                    scoring_types.append(goal_type.name)
                    
                for match in all_matches_list:
                    total_goals_for += match.home_score if match.home_team == self.team else match.away_score
                    total_goals_against += match.away_score if match.home_team == self.team else match.home_score
                
                await self.send(text_data=json.dumps({
                    'command': 'goal_stats',
                    'goal_stats': goal_stats,
                    'scoring_types': scoring_types,
                    'played_matches': played_matches,
                    'total_goals_for': total_goals_for,
                    'total_goals_against': total_goals_against,
                }))
                
            elif command == "spelers":
                if 'season_uuid' in json_data:
                    season_uuid = json_data['season_uuid']
                else:
                    season_uuid = None
                
                # Initialize an empty list to store players
                players_in_team_season = []

                # Check if a specific season is provided
                if season_uuid:
                    # Assuming you have a Season object or its UUID
                    season = await sync_to_async(Season.objects.get)(id_uuid=season_uuid)

                    # Get all TeamData instances for the specified team and season
                    team_data_instances = await sync_to_async(list)(TeamData.objects.prefetch_related('players').filter(team=self.team, season=season))

                    # Iterate through the TeamData instances and collect players
                    for team_data_instance in team_data_instances:
                        all_players = await sync_to_async(team_data_instance.players.all)()
                        players_prefetch = await sync_to_async(all_players.prefetch_related)('user')
                        await sync_to_async(players_in_team_season.extend)(players_prefetch)
                else:
                    # No specific season provided, so retrieve players from all seasons
                    all_team_data_instances = await sync_to_async(list)(TeamData.objects.prefetch_related('players').filter(team=self.team))

                    # Iterate through all TeamData instances and collect players
                    for team_data_instance in all_team_data_instances:
                        all_players = await sync_to_async(team_data_instance.players.all)()
                        players_prefetch = await sync_to_async(all_players.prefetch_related)('user')
                        await sync_to_async(players_in_team_season.extend)(players_prefetch)
                        
                players_in_team_season_list = await sync_to_async(list)(players_in_team_season)
                        
                players_in_team_season_dict = [
                    {
                        'id': str(player.id_uuid),
                        'name': player.user.username,
                        'profile_picture': player.profile_picture.url if player.profile_picture else None,
                        'get_absolute_url': str(player.get_absolute_url())
                    }
                    for player in players_in_team_season_list
                ]

                await self.send(text_data=json.dumps({
                    'command': 'spelers',
                    'spelers':players_in_team_season_dict,
                }))
                
            elif command == "follow":
                follow = json_data['followed']
                user_id = json_data['user_id']
                
                player = await sync_to_async(Player.objects.get)(user=user_id)
                
                if follow:
                    await sync_to_async(player.team_follow.add)(self.team)
                    
                else:
                    await sync_to_async(player.team_follow.remove)(self.team)
                
                await self.send(text_data=json.dumps({
                    'command': 'follow',
                    'status': 'success'
                }))
                    
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            }))
            
class profile_data(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.player = None
        self.user_profile = None
        
    async def connect(self):
        player_id = self.scope['url_route']['kwargs']['id']
        self.player = await sync_to_async(Player.objects.prefetch_related('user').get)(id_uuid=player_id)
        self.user = self.player.user
        self.user_profile = await sync_to_async(UserProfile.objects.get)(user=self.user)
        await self.accept()
        
    async def disconnect(self, close_code):
        pass
    
    async def receive(self, text_data):
        try:
            json_data = json.loads(text_data)
            command = json_data['command']
            
            if command == "player_stats":
                total_goals_for = 0
                total_goals_against = 0
                
                all_matches_with_player = await sync_to_async(Match.objects.filter)(
                    Q(home_team__team_data__players=self.player, finished=True) |
                    Q(away_team__team_data__players=self.player, finished=True)
                )

                goal_types = await sync_to_async(list)(GoalType.objects.all())

                player_goal_stats = {}
                scoring_types = []

                for goal_type in goal_types:
                    goals_by_player = await sync_to_async(Goal.objects.filter(
                        match__in=all_matches_with_player, 
                        goal_type=goal_type, 
                        player=self.player,
                        for_team=True
                    ).count)()
                    
                    goals_against_player = await sync_to_async(Goal.objects.filter(
                        match__in=all_matches_with_player, 
                        goal_type=goal_type, 
                        player=self.player,
                        for_team=False
                    ).count)()

                    player_goal_stats[goal_type.name] = {
                        "goals_by_player": goals_by_player,
                        "goals_against_player": goals_against_player
                    }
                    
                    total_goals_for += goals_by_player
                    total_goals_against += goals_against_player

                    scoring_types.append(goal_type.name)

                await self.send(text_data=json.dumps({
                    'command': 'player_goal_stats',
                    'player_goal_stats': player_goal_stats,
                    'scoring_types': scoring_types,
                    'played_matches': await sync_to_async(all_matches_with_player.count)(),
                    'total_goals_for': total_goals_for,
                    'total_goals_against': total_goals_against,
                }))
                
            if command == "settings_request":
                await self.send(text_data=json.dumps({
                    'command': 'settings_request',
                    'username': self.user.username,
                    'email': self.user.email,
                    'first_name': self.user.first_name,
                    'last_name': self.user.last_name,
                    'is_2fa_enabled': self.user_profile.is_2fa_enabled
                }))
            
            if command == "settings_update":
                data = json_data['data']
                username = data['username']
                email = data['email']
                first_name = data['first_name']
                last_name = data['last_name']
                is_2fa_enabled = data['is_2fa_enabled']
                
                self.user.username = username
                self.user.email = email
                self.user.first_name = first_name
                self.user.last_name = last_name
                await sync_to_async(self.user.save)()
                
                self.user_profile.is_2fa_enabled = is_2fa_enabled
                await sync_to_async(self.user_profile.save)()
                
                await self.send(text_data=json.dumps({
                    'command': 'settings_updated',
                }))
                
            if command == 'update_profile_picture_url':
                url = json_data['url']
                if url:
                    self.player.profile_picture = url  # Assuming 'url' contains the relative path of the image
                    await sync_to_async(self.player.save)()

                    # Send a response back to the client if needed
                    await self.send(text_data=json.dumps({
                        'command': 'profile_picture_updated',
                        'status': 'success'
                    }))
                    
            if command == 'teams':
                teams = await sync_to_async(list)(Team.objects.filter(team_data__players=self.player))
                
                teams_dict = [
                    {
                        'id': str(team.id_uuid),
                        'name': team.name,
                        'get_absolute_url': str(team.get_absolute_url())
                    }
                    for team in teams
                ]
                
                await self.send(text_data=json.dumps({
                    'command': 'teams',
                    'teams': teams_dict
                }))
                
            if command == "upcomming_matches":
                upcomming_matches = await sync_to_async(list)(Match.objects.prefetch_related('home_team', 'away_team').filter(
                    Q(home_team__team_data__players=self.player, finished=False) |
                    Q(away_team__team_data__players=self.player, finished=False)
                ))
                
                upcomming_matches_dict = await transfrom_matchdata(upcomming_matches)
                
                await self.send(text_data=json.dumps({
                    'command': 'upcomming-matches',
                    'matches': upcomming_matches_dict
                }))
                
            if command == "past_matches":
                upcomming_matches = await sync_to_async(list)(Match.objects.prefetch_related('home_team', 'away_team').filter(
                    Q(home_team__team_data__players=self.player, finished=True) |
                    Q(away_team__team_data__players=self.player, finished=True)
                ))
                
                upcomming_matches_dict = await transfrom_matchdata(upcomming_matches)
                
                await self.send(text_data=json.dumps({
                    'command': 'past-matches',
                    'matches': upcomming_matches_dict
                }))
            
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            }))
            
async def transfrom_matchdata(wedstrijden_data):
    wedstrijden_dict = []
            
    for wedstrijd in wedstrijden_data:
        locale.setlocale(locale.LC_TIME, 'nl_NL.utf8')
        start_time_dt = datetime.fromisoformat(wedstrijd.start_time.isoformat())
        
        # Format the date as "za 01 april"
        formatted_date = start_time_dt.strftime("%a %d %b").lower()  # %a for abbreviated day name

        # Extract the time as "14:45"
        formatted_time = start_time_dt.strftime("%H:%M")

        wedstrijden_dict.append({
            'id_uuid': str(wedstrijd.id_uuid),
            'home_team': wedstrijd.home_team.name,
            'away_team': wedstrijd.away_team.name,
            'home_score': wedstrijd.home_score,
            'away_score': wedstrijd.away_score,
            'start_date': formatted_date,
            'start_time': formatted_time,  # Add the time separately
            'length': wedstrijd.length,
            'finished': wedstrijd.finished,
            'winner': wedstrijd.get_winner().name if wedstrijd.get_winner() else None,
            'get_absolute_url': str(wedstrijd.get_absolute_url())
        })
        
    return wedstrijden_dict

class club_data(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.player = None
        self.user_profile = None
        self.club = None
        
    async def connect(self):
        self.club = self.scope['url_route']['kwargs']['id']
        await self.accept()
        
    async def disconnect(self, close_code):
        pass
    
    async def receive(self, text_data):
        try:
            json_data = json.loads(text_data)
            command = json_data['command']
            
            if command == "teams":
                teams = await sync_to_async(list)(Team.objects.filter(club=self.club))
                
                teams_json = [
                    {
                        'id': str(team.id_uuid),
                        'name': team.name,
                        'get_absolute_url': str(team.get_absolute_url())
                    }
                    for team in teams
                ]
                
                await self.send(text_data=json.dumps({
                    'command': 'teams',
                    'teams': teams_json
                }))
            
            elif command == "wedstrijden":
                teams = await sync_to_async(list)(Team.objects.filter(club=self.club))
                team_ids = [team.id_uuid for team in teams]
                wedstrijden_data = await sync_to_async(list)(Match.objects.prefetch_related('home_team', 'away_team').filter(Q(home_team__in=team_ids) | Q(away_team__in=team_ids), finished=False).order_by('start_time'))
                
                wedstrijden_dict = await transfrom_matchdata(wedstrijden_data)
                
                await self.send(text_data=json.dumps({
                    'command': 'wedstrijden',
                    'wedstrijden': wedstrijden_dict
                }))
                
            elif command == "ended_matches":
                teams = await sync_to_async(list)(Team.objects.filter(club=self.club))
                team_ids = [team.id_uuid for team in teams]
                wedstrijden_data = await sync_to_async(list)(Match.objects.prefetch_related('home_team', 'away_team').filter(Q(home_team__in=team_ids) | Q(away_team__in=team_ids), finished=True).order_by('-start_time'))
                
                wedstrijden_dict = await transfrom_matchdata(wedstrijden_data)
                
                await self.send(text_data=json.dumps({
                    'command': 'wedstrijden',
                    'wedstrijden': wedstrijden_dict
                }))
            
            elif command == "follow":
                follow = json_data['followed']
                user_id = json_data['user_id']
                
                player = await sync_to_async(Player.objects.get)(user=user_id)
                
                if follow:
                    await sync_to_async(player.club_follow.add)(self.club)
                    
                else:
                    await sync_to_async(player.club_follow.remove)(self.club)
                
                await self.send(text_data=json.dumps({
                    'command': 'follow',
                    'status': 'success'
                }))
            
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            }))