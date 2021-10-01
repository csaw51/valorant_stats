import requests
import re
from bs4 import BeautifulSoup
from collections import defaultdict
import json

HEADERS = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
           'accept-encoding': 'gzip, deflate, br',
           'accept-language': 'en-US,en;q=0.9',
           'cache-control': 'max-age=0',
           'sec-ch-ua': '"Chromium";v="94", "Google Chrome";v="94", ";Not A Brand";v="99"',
           'sec-ch-ua-mobile': '?0',
           'sec-ch-ua-platform': '"Windows"',
           'sec-fetch-dest': 'document',
           'sec-fetch-mode': 'navigate',
           'sec-fetch-site': 'none',
           'sec-fetch-user': '?1',
           'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36'}


class MapProcessor:
    def __init__(self, map_details):
        self.map_raw = map_details
        self.map_name = self.map_raw.find(class_='map-name').text.strip()
        self.team_aliases = self.get_team_aliases()
        self.team_alias_map = {i: k for k, v in self.team_aliases.items() for i in v}
        self.timeline = self.map_raw.find(class_='stat-wrap timeline-wrapper')

    
    def __get_round_breakdown(self, round_breakdown, breakdown_class):
        data = {}
        breakdown = round_breakdown.find(class_=breakdown_class)
        for i in breakdown.find_all(class_='team-logo'):
            for team, aliases in self.team_aliases.items(): 
                if set(i.attrs['class']) & aliases:
                    data[team] = i.text.strip()

        return data

    def __format_stats_table(self, stats, col_cnt=6, row_cnt=7):
        keys = [stats[r].text.strip() for r in range(0, row_cnt)]
        key_map = {'Player': 'player_name',
                   '': 'agent',
                   'SCORE': 'combat_score',
                   'K': 'kills',
                   'A': 'assists'}

        table = []
        ind = row_cnt
        for c in range(1, col_cnt):
            row_vals = {}
            
            for r in range(0, row_cnt):
                cleaned_key = key_map.get(keys[r])
                cleaned_vals = [i.strip() for i in stats[ind].text.splitlines() if i]

                if len(cleaned_vals) == 1:
                    row_vals[cleaned_key] = cleaned_vals[0]

                if not cleaned_key:
                    if keys[r] == 'ECON':
                        row_vals.update(dict(zip(['money_start', 'money_remaining'], cleaned_vals)))

                    if keys[r] == 'EQUIP':
                        row_vals.update(dict(zip(['gun', 'armor'], cleaned_vals)))
                ind += 1

            table.append(row_vals)

        return table

    def __get_deaths_per_round(self, rnd):
        aliases = ['team_one', 'team_two']
        re_compiled = re.compile(r'\S+agents%2F([a-z]+)[-|_]\S+')
        deaths_in_timeline = rnd.find(class_='timeline').find_all(class_='enemy')
        data = defaultdict(list)

        for d in deaths_in_timeline:
            for a in aliases:
                try:
                    re_search = re_compiled.match(d.find(class_=a).attrs.get('src'))
                    data[self.team_alias_map[a]].append(re_search.group(1))

                except AttributeError:
                    pass

        return data

    def __combine_player_stats(self, player_stats, deaths, player_agents):
        for team, players in player_stats.items():
            for player in players:
                agent = player_agents[team][player['player_name']]
                player['agent'] = agent
                player['death'] = 1 if agent in deaths[team] else 0

        return player_stats

    def get_map_name(self):
        return self.map_name

    def get_team_aliases(self):
        try:
            return self.team_aliases

        except AttributeError:
            aliases = {'team-1': {'team-one', 'team-1', 'home-team', 'green'},
                       'team-2': {'team-two', 'team-2', 'away-team', 'purple'}}
            return {self.map_raw.find(class_='team-col first-half') \
                                .find(class_=f'team-line {alias}') \
                                .find(class_='team-name').text.strip(): aliases[alias]
                    for alias in aliases}

    def get_player_agents(self):
        teams = {}
        team_stats = self.map_raw.find(class_='overview-wrapper').find_all(class_='match-stat-wrap')
        
        for team in team_stats:
            players = {}
            team_name = team.find(class_='stats-team-name').find(class_='name').text.strip()
            player_stats = team.find_all(class_='single-row element-trim-button main-area-default')
            
            for p in player_stats:
                # The below is equivalent to:
                # players[player_name] = agent_name
                players[p.find('a').text.strip()] = p.find('img').attrs['title'].strip()

            teams[team_name] = players

        return teams

    def process_timeline(self):
        data = defaultdict(dict)
        player_agents = self.get_player_agents()
        rounds = self.timeline.find_all(class_='round-data')
        rnd_counter = 1
        for rnd in rounds:
            rnd_key = f'round_{rnd_counter}'
            player_data = self.get_player_data_by_round(rnd, player_agents)
            team_data = self.get_team_data_by_round(rnd)

            for t in self.team_aliases.keys():
                data[rnd_key][t] = {'player_stats': player_data[t],
                                    'team_data': team_data[t]}
            rnd_counter += 1

        return data

    def get_player_data_by_round(self, rnd, player_agents):
        aliases = ['home-team', 'away-team']
        data = {}

        for alias in aliases:
            team_name = self.team_alias_map[alias]
            raw_stats = rnd.find(class_=f'round-stats {alias}') \
                           .find_all(class_=re.compile('single-(column|stat)'))
            data[team_name] = self.__format_stats_table(raw_stats)

        deaths = self.__get_deaths_per_round(rnd)
        return self.__combine_player_stats(data, deaths, player_agents)

    def get_team_data_by_round(self, rnd):
        round_breakdown = rnd.find(class_='round-breakdown main-area-alt element-trim-normal')
        victory_info = round_breakdown.find('span')
        data = {team: {'victory': True if set(victory_info.attrs['class']) & aliases else False,
                       'victory_type': victory_info.text} 
                for team, aliases in self.team_aliases.items()}

        breakdown_classes = ['round-bank', 'round-loadout']
        for c in breakdown_classes:
            breakdown_details = self.__get_round_breakdown(round_breakdown, c)
            for t, value in breakdown_details.items():
                if c == 'round-bank':
                    data[t].update({'money_total': value})
                if c == 'round-loadout':
                    data[t].update({'avg_loadout': value})

        return data

def get_match_details(soup):
    data = {}
    maps = soup.find_all(class_=re.compile(r'map-wrapper map_[0-9]*'))

    for m in maps:
        processed_map = MapProcessor(m)
        data[processed_map.map_name] = processed_map.process_timeline()

    return data


def read_html_file(filename):
    with open(filename, 'r') as fp:
        return fp.read()


def get_match_links_from_event(soup):
    links = {}
    matches = soup.body.find(id='match-overview')
    
    for game in matches.find_all('a'):
        teams = '-'.join([team.strip() for team in game.find(class_='match-info-match').text.split('vs')])
        links[teams] = game.attrs.get('href')

    return links


def get_event_name(soup):
    return soup.body.find(class_='event-information').find('h1').text


if __name__ == '__main__':
    project_dir = 'E:/Python_Project/valorant_stats'

    # event_file = project_dir + '/data/example_event_page.html'
    # event_html_str = read_html_file(event_file)
    # event_soup = BeautifulSoup(event_html_str, 'html.parser')
    
    match_file = project_dir + '/data/game_1_berlin.html'
    match_html_str = read_html_file(match_file)
    match_soup = BeautifulSoup(match_html_str, 'lxml')
    print(json.dumps(get_match_details(match_soup)))