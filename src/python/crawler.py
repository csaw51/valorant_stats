import requests
import re
from bs4 import BeautifulSoup

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


def get_match_details(soup):
    data = {}
    maps = soup.find_all(class_=re.compile(r'map-wrapper map_[0-9]*'))

    for m in maps:
        teams = get_team_mappings(m)
        round_data = process_timeline(m.find(class_='stat-wrap timeline-wrapper'))
        map_name = get_map_name(m)
        data[map_name] = round_data

    return data


def process_timeline(timeline):
    data = {}
    rounds = timeline.find_all(class_='round-data')
    rnd_counter = 1

    for rnd in rounds:
        rnd_key = f'round_{rnd_counter}'

        data[rnd_key] = get_player_data(rnd)
        rnd_counter += 1

    return data


def get_map_name(map_info):
    return map_info.find(class_='map-name').text


def get_team_mappings(map_info):
    team_1_name = map_info.find(class_='team-col first-half').find(class_='team-line team-1').find(class_='team-name').text
    team_2_name = map_info.find(class_='team-col first-half').find(class_='team-line team-2').find(class_='team-name').text
    return {'team-one': team_1_name,
            'team-1': team_1_name,
            'home-team': team_1_name,
            'team-two': team_2_name,
            'team-2': team_2_name,
            'away-team': team_2_name}


def get_team_data(rnd):
    pass


def get_player_data(rnd):
    data = {'player_stats': {'home-team': None,
                             'away-team': None},
            'deaths': None}

    for k, v in data['player_stats'].items():
        raw_stats = v.find_all(class_=re.compile('single-(column|stat)'))
        data['player_stats'][k] = format_stats_table(raw_stats)
    
    data['deaths'] = get_deaths_per_round(rnd)

    return data


def format_stats_table(stats, col_cnt=6, row_cnt=7):
    ind = row_cnt
    table = []
    keys = [stats[r].text.strip() for r in range(0, row_cnt)]
    key_map = {'Player': 'player_name',
               '': 'agent',
               'SCORE': 'combat_score',
               'K': 'kills',
               'A': 'assists'}

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


def get_deaths_per_round(rnd):
    re_compiled = re.compile(r'\S+agents%2F([a-z]+)[-|_]\S+')
    deaths = {'team-two': [],
              'team-one': []}
    deaths_in_timeline = rnd.find(class_='timeline').find_all(class_='enemy')

    for d in deaths_in_timeline:
        for k in deaths.keys():
            try:
                re_search = re_compiled.match(d.find(class_=k).attrs.get('src'))
                deaths[k].append(re_search.group(1))

            except AttributeError:
                pass

    return deaths


if __name__ == '__main__':
    project_dir = 'E:/Python_Project/valorant_stats'

    # event_file = project_dir + '/data/example_event_page.html'
    # event_html_str = read_html_file(event_file)
    # event_soup = BeautifulSoup(event_html_str, 'html.parser')
    
    match_file = project_dir + '/data/game_1_berlin.html'
    match_html_str = read_html_file(match_file)
    match_soup = BeautifulSoup(match_html_str, 'html.parser')
    #print(get_team_mapping(match_soup))
    get_match_details(match_soup)