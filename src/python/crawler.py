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
    maps = match_soup.find_all(class_=re.compile(r'map-wrapper map_[0-9]*'))

    for m in maps:
        timeline = m.find(class_='stat-wrap timeline-wrapper')
        round_data = process_timeline(timeline)
        break
        map_name = get_map_name(m)

        data[map_name] = round_data

    return data


def process_timeline(timeline):
    rounds = timeline.find_all(class_='round-data')
    print(get_player_data(rounds[0]))


def get_team_data(rnd):
    pass


def get_player_data(rnd):
    home_team_data = rnd.find(class_='home-team')
    home_team_stats = [i.text.strip() 
                       for i in home_team_data.find_all(class_=re.compile('single-(column|stat)'))]

    away_team_data = rnd.find(class_='away-team')
    away_team_stats = [i.text.strip() 
                       for i in away_team_data.find_all(class_=re.compile('single-(column|stat)'))]
    
    home_stats = format_table(home_team_stats)
    away_stats = format_table(away_team_stats)
    return home_stats, away_stats

def format_table(stats, col=6, row=7):
    ind = row
    table = []
    keys = [stats[r] for r in range(0, row)]

    for c in range(1, col):
        row_vals = {}
        
        for r in range(0, row):
            if stats[ind]:
                row_vals[keys[r]] = stats[ind]
            ind += 1

        table.append(row_vals) 

    for r in table:
        cleaned_equip = [i.strip() for i in r['EQUIP'].splitlines() if i]
        cleaned_econ = [i.strip() for i in r['ECON'].splitlines() if i]
        r.update({'money_start': cleaned_econ[0],
                  'money_remaining': cleaned_econ[1],
                  'gun': cleaned_equip[0],
                  'armor': cleaned_equip[1]})
        del r['EQUIP']
        del r['ECON']

    return table


def get_map_name(map_info):
    pass


if __name__ == '__main__':
    project_dir = 'E:/Python_Project/valorant_stats'

    # event_file = project_dir + '/data/example_event_page.html'
    # event_html_str = read_html_file(event_file)
    # event_soup = BeautifulSoup(event_html_str, 'html.parser')
    
    match_file = project_dir + '/data/game_1_berlin.html'
    match_html_str = read_html_file(match_file)
    match_soup = BeautifulSoup(match_html_str, 'html.parser')
    get_match_details(match_soup)