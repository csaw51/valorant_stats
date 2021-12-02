import requests
import re
import json
import csv
import logging
import lxml
import time
from bs4 import BeautifulSoup
from collections import defaultdict


class EventNotFound(Exception):
    pass


class ConnectionHandler:
    def __init__(self):
        self.protocol = 'https'
        self.hostname = 'www.thespike.gg'
        self.basepath = f'{self.protocol}://{self.hostname}'
        self.sess = requests.Session()

    def __request(self, path, params=None, headers=None):
        url = f'{self.basepath}{path}'
        logging.info(url)

        resp = self.sess.get(url, params=params, headers=headers)

        try:
            resp.raise_for_status()
            logging.debug(f'Response status code: {resp.status_code}')
            return BeautifulSoup(resp.text, 'lxml')

        except requests.HTTPError as e:
            logging.debug(f'Response headers: {resp.headers}')
            logging.debug(f'Response text: {resp.text}')
            logging.error(f'Error making request: {e}')
            raise e

    def get_events(self):
        return self.__request('/events/completed')

    def get_event_by_name(self, event_name):
        soup = self.get_events()
        events = soup.body.find(class_='events-overview-lists').find_all(class_='single-event')
        for event in events:
            if event_name == event.find('h3').text:
                logging.info(f'Found event named: {event_name}')
                endpoint = event.find('a').attrs.get('href')
                url = endpoint.split('/')
                url.insert(2, 'results')
                return self.__request('/'.join(url))
        raise EventNotFound()

    def get_match(self, match_link):
        return self.__request(match_link)


class ValorantEvent:
    def __init__(self, event_soup):
        self.event_raw = event_soup
        self.name = self.event_raw.body.find(class_='event-information').find('h1').text
        self.match_links = {}

    def get_match_links_from_event(self):
        logging.info(f'Searching for match links in event: {self.name}')
        if not self.match_links:
            matches = self.event_raw.body.find(id='match-overview')

            for game in matches.find_all('a'):
                teams = '-'.join([team.strip() for team in game.find(class_='match-info-match').text.split('vs')])
                self.match_links[teams] = game.attrs.get('href')

        logging.debug(f'Match links found in event: {self.match_links}')
        return self.match_links

    def get_event_name(self):
        return self.name


class MapProcessor:
    def __init__(self, map_details):
        self.map_raw = map_details
        self.map_name = self.map_raw.find(class_='map-name').text.strip()
        self.team_aliases = self.get_team_aliases()
        self.team_alias_map = {i: k for k, v in self.team_aliases.items() for i in v}
        self.timeline = self.map_raw.find(class_='stat-wrap timeline-wrapper hidden')

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
        aliases = ['team-one', 'team-two']
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
                player['death'] = 1 if agent.lower() in deaths[team] else 0

        return player_stats

    def __get_opposite_value(self, array, value):
        ele_set = set(array)
        val_set = set([value])
        return (ele_set - val_set).pop()

    def __map_rounds_to_halves(self, round_num, side_data):
        pass

    def get_map_name(self):
        return self.map_name

    def get_team_aliases(self):
        try:
            return self.team_aliases

        except AttributeError:
            aliases = {'team-1': {'team-one', 'team-1', 'home-team', 'green'},
                       'team-2': {'team-two', 'team-2', 'away-team', 'purple'}}
            return {self.map_raw.find(class_='team-col first-half')
                                .find(class_=f'team-line {alias}')
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
                player_name = p.find('a').text.strip()
                agent_name = p.find('img').attrs['title'].strip()
                players[player_name] = agent_name

            teams[team_name] = players

        return teams

    def get_sides(self):
        side_results = {}
        halves = ['first-half', 'second-half']
        aliases = ['team-1', 'team-2']
        side_data = self.timeline.find(class_='round-detail-wrapper')
        for half in halves:
            half_results = {}
            half_data = side_data.find(class_=half)

            for alias in aliases:
                team_name = self.team_alias_map[alias]
                half_results[team_name] = half_data.find(class_=alias).find(class_='side').text

            side_results[half] = half_results

        try:
            ot_data = self.timeline.find(class_='overtime-breakdown')
            side_results['overtime'] = {}
            for ot_round in ot_data.find_all(class_='single-round'):
                round_num = ot_round.find(class_='round-number').text
                for alias in aliases:
                    team_name = self.team_alias_map[alias]
                    try:
                        ot_side = ot_round.find(class_=f'round-side {alias}').text
                        side_results['overtime'][round_num] = {team_name: ot_side}

                    except Exception:
                        pass

        except AttributeError:
            logging.debug(f'No overtime found for {self.map_name}')

        return side_results

    def get_side_data_by_round(self, round_num, side_data):
        if round_num in range(1, 13):
            return side_data['first-half']

        elif round_num in range(13, 25):
            return side_data['second-half']

        else:
            return side_data['overtime'][str(round_num)]

    def process_map_timeline(self):
        logging.info(f'Processing timeline for map: {self.map_name}')

        data = defaultdict(dict)
        player_agents = self.get_player_agents()
        rounds = self.timeline.find_all(class_='round-data')
        sides = self.get_sides()
        side_map = ['Def', 'Atk']

        rnd_counter = 1
        for rnd in rounds:
            logging.info(f'Getting stats for round {rnd_counter}')
            player_data = self.get_player_data_by_round(rnd, player_agents)
            team_data = self.get_team_data_by_round(rnd)
            side_data = self.get_side_data_by_round(rnd_counter, sides)

            for t in self.team_aliases.keys():
                try:
                    side_stats = side_data[t]

                except KeyError:
                    team = self.__get_opposite_value(self.team_aliases.keys(), t)
                    side_stats = self.__get_opposite_value(side_map, side_data[team])

                data[rnd_counter][t] = {'player_stats': player_data[t],
                                        'team_data': team_data[t],
                                        'side_data': side_stats}
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
                    data[t].update({'loadout_avg': value})

        return data


def get_match_details(soup):
    data = {}
    maps = soup.find_all(class_=re.compile(r'map-wrapper map_[0-9]*'))

    for m in maps:
        processed_map = MapProcessor(m)
        data[processed_map.map_name] = processed_map.process_map_timeline()

    return data


def read_html_file(filename):
    with open(filename, 'r') as fp:
        return fp.read()


# Instead of a DB, I am going to store the data as flat tables
def flatten_match_stats(match_name, match_data):
    logging.info(f'Processing stats for match: {match_name}')
    player_by_round = []
    team_by_round = []

    for map_name, map_stats in match_data.items():
        for round_num, round_stats in map_stats.items():
            for team_name, team_data in round_stats.items():
                team_by_round.append({'match_name': match_name,
                                      'map_name': map_name,
                                      'round_num': round_num,
                                      'team_name': team_name,
                                      'side': team_data['side_data'],
                                      'victory': team_data['team_data']['victory'],
                                      'victory_type': team_data['team_data']['victory_type'],
                                      'money_total': team_data['team_data']['money_total'],
                                      'loadout_avg': team_data['team_data']['loadout_avg']})

                for player in team_data['player_stats']:
                    player_by_round.append({'match_name': match_name,
                                            'map_name': map_name,
                                            'round_num': round_num,
                                            'team_name': team_name,
                                            'side': team_data['side_data'],
                                            'player_name': player['player_name'],
                                            'combat_score': player['combat_score'],
                                            'kills': player['kills'],
                                            'assists': player['assists'],
                                            'money_start': player['money_start'],
                                            'money_remaining': player['money_remaining'],
                                            'gun': player['gun'],
                                            'armor': player['armor'],
                                            'agent': player['agent'],
                                            'death': player['death']})

    return player_by_round, team_by_round


def write_event_stats(data, event_name, data_type):
    filename = f'E:/Python_Project/valorant_stats/data/{event_name}_{data_type}.csv'

    with open(filename, 'w', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=data[0].keys())
        writer.writeheader()

        for row in data:
            writer.writerow(row)


def read_json(filename):
    with open(filename, 'r') as fp:
        return json.load(fp)


def process_event(event_name):
    conn = ConnectionHandler()
    try:
        event_soup = conn.get_event_by_name(event_name)

    except EventNotFound:
        msg = f'No event found with the name: {event_name}'
        logging.error(msg)
        raise EventNotFound(msg)

    event = ValorantEvent(event_soup)
    logging.info(event.name)
    match_links = event.get_match_links_from_event()
    team_event_stats = []
    player_event_stats = []
    for match_name, match_link in match_links.items():
        logging.info(f'Getting stats for match: {match_name}')
        match_soup = conn.get_match(match_link)
        details = get_match_details(match_soup)
        flattened_stats = flatten_match_stats(match_name, details)
        player_event_stats.extend(flattened_stats[0])
        team_event_stats.extend(flattened_stats[1])
        time.sleep(10.0)

    cleaned_name = event_name.split(':')[0]
    write_event_stats(team_event_stats, cleaned_name, 'team-stats')
    write_event_stats(player_event_stats, cleaned_name, 'player-stats')


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - [%(levelname)s] - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level='DEBUG')
    logging.info('Start')
    # config = read_json(sys.argv[1])
    event_name = 'VCT Stage 3: Masters - Berlin - Playoffs'
    process_event(event_name)
