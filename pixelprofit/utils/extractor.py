from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from fuzzywuzzy import fuzz
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
import pandas as pd
import numpy as np
import re
import time

# Configure Selenium
options = Options()
options.add_argument("--headless")  # Run in headless mode
options.add_argument("--disable-gpu")  # Disable GPU acceleration
options.add_argument("--no-sandbox")  # Bypass OS security model
options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems

# Path to your ChromeDriver
driver_path = "chromedriver"

class extractor():
    def __init__(self):
        self.driver = webdriver.Chrome(options=options)
    
    def __del__(self):
        self.driver.quit()
        
    def get_all(self, matchDf: pd.DataFrame):
        betDf = pd.DataFrame({'MatchID': pd.Series(dtype='str'), 'Team A': pd.Series(dtype='str'), 'Team B': pd.Series(dtype='str'), 'Bet Type': pd.Series(dtype='str'), 'Bet Return A': pd.Series(dtype='float'), 'Bet Return B': pd.Series(dtype='float'), 'Bet Website': pd.Series(dtype='str'), 'Bet Link': pd.Series(dtype='str'), 'Data Datetime': pd.Series(dtype='datetime64[ns]'), 'Data Source': pd.Series(dtype='str')})
        betDf = pd.concat([betDf, self.get_pinnacle(matchDf)], ignore_index=True)
        betDf = pd.concat([betDf, self.get_vlrgg(matchDf)], ignore_index=True)
        betDf.join(matchDf[['Datetime', 'Match Link']], on='MatchID')
        return betDf
        
    def get_pinnacle(self, matchDf: pd.DataFrame):
        actions = ActionChains(self.driver)
        # Navigate to the target URL
        url = 'https://www.pinnacle.com/en/esports/games/valorant/matchups'
        self.driver.get(url)
        time.sleep(6)  # Wait for the page to load
        matchList = set()
        
        html_in_view = self.driver.page_source
        temp_soup = BeautifulSoup(html_in_view, 'html.parser')
        matchItems = temp_soup.find_all('div', class_=re.compile(r'^row-'))
        for item in matchItems:
            matchList.add(item)

        matchDf['Team Concat'] = matchDf['Team A'].str.lower().str.replace(' ', '') + matchDf['Team B'].str.lower().str.replace(' ', '')

        pinnacleTeamLUT = {
            'SoloMid': 'TSM',
            'Alpha D': 'esports team αD'
        }

        betDf = pd.DataFrame({'MatchID': pd.Series(dtype='str'), 'Team A': pd.Series(dtype='str'), 'Team B': pd.Series(dtype='str'), 'Bet Type': pd.Series(dtype='str'), 'Bet Return A': pd.Series(dtype='float'), 'Bet Return B': pd.Series(dtype='float'), 'Bet Website': pd.Series(dtype='str'), 'Bet Link': pd.Series(dtype='str'), 'Data Datetime': pd.Series(dtype='datetime64[ns]')})
        
        for match in matchList:
            matchData = match.find_all(string=True)
            pattern = r'^(.*?)\s*\(([^)]+)\)'
            teamAData = re.match(pattern, matchData[0])
            if not teamAData:
                continue
            
            teamBData = re.match(pattern, matchData[1])
            assert(teamAData.group(2) == teamBData.group(2))        
            
            teamA = teamAData.group(1) if teamAData.group(1) not in pinnacleTeamLUT.keys() else pinnacleTeamLUT[teamAData.group(1)]
            teamB = teamBData.group(1) if teamBData.group(1) not in pinnacleTeamLUT.keys() else pinnacleTeamLUT[teamBData.group(1)]
            betType = teamAData.group(2)

            combinedTeam = teamA.lower().replace(' ', '') + teamB.lower().replace(' ', '')
            combinedTeamRev = teamB.lower().replace(' ', '') + teamA.lower().replace(' ', '')
            avilableMatches = matchDf['Team Concat'].values
            if combinedTeam in avilableMatches or combinedTeamRev in avilableMatches:
                matchID = matchDf[(matchDf['Team Concat'] == combinedTeam) | (matchDf['Team Concat'] == combinedTeamRev)].index[0]
                print(f'🟢 Exact Match Found ({matchID})')
                teamA = matchDf.loc[matchID]["Team A"]
                teamB = matchDf.loc[matchID]["Team B"]
                teamA_odds = float(matchData[3])
                teamB_odds = float(matchData[4])
                found = True
            else:
                found = False
                for index, row in matchDf.iterrows():
                    # print(f'Checking {row["Team A"]} vs {row["Team B"]} ({fuzz.partial_ratio(row["Team A"], teamA)}, {fuzz.partial_ratio(row["Team B"], teamB)})')
                    ratioSetA = [fuzz.partial_ratio(row["Team A"].lower(), teamA.lower()), fuzz.partial_ratio(row["Team B"].lower(), teamB.lower())]
                    ratioSetB = [fuzz.partial_ratio(row["Team A"].lower(), teamB.lower()), fuzz.partial_ratio(row["Team B"].lower(), teamA.lower())]
                    if (ratioSetA[0] > 66 and ratioSetA[1] > 66):
                        print(f'🔵 Fuzzy Match Found ({row["Team A"]} vs {row["Team B"]}) ({ratioSetA}) ({index})')
                        matchID = index
                        teamA = row["Team A"]
                        teamB = row["Team B"]
                        teamA_odds = float(matchData[3])
                        teamB_odds = float(matchData[4])
                        found = True
                        break
                    elif (ratioSetB[0] > 66 and ratioSetB[1] > 66):
                        print(f'🔵 Reverse Fuzzy Match Found ({row["Team A"]} vs {row["Team B"]}) ({ratioSetB}) ({index})')
                        matchID = index
                        teamA = row["Team A"]
                        teamB = row["Team B"]
                        teamA_odds = float(matchData[4])
                        teamB_odds = float(matchData[3])
                        found = True
                        break
                if not found:
                    print('🔴 Match Not Found')
                    continue
            
            betting_link = urljoin(url, match.find('a')['href'])
            print(f'🔵 [{matchID}] {teamA} vs {teamB} ({betType})')
            print(f'pinnacle - {teamA_odds} vs {teamB_odds} @ {betting_link}')
            matchDf.at[matchID, 'Pinnacle Odds'] = matchData[2]
            
            tempDf = pd.DataFrame({'MatchID': [matchID], 'Team A': [teamA], 'Team B': [teamB], 'Bet Type': [betType], 'Bet Return A': [teamA_odds], 'Bet Return B': [teamB_odds], 'Bet Website': 'pinnacle', 'Bet Link': [betting_link]})
            betDf = pd.concat([betDf, tempDf], ignore_index=True)
        
        betDf['Data Datetime'] = pd.Timestamp.now()
        betDf['Data Source'] = 'Pinnacle'
        return betDf
    
    def get_vlrgg(self, matchDf: pd.DataFrame, delay: int = .2):
        matchDf = matchDf.reset_index().to_dict('records')
        betDf = pd.DataFrame({'MatchID': pd.Series(dtype='str'), 'Team A': pd.Series(dtype='str'), 'Team B': pd.Series(dtype='str'), 'Bet Return A': pd.Series(dtype='float'), 'Bet Return B': pd.Series(dtype='float'), 'Bet Website': pd.Series(dtype='str'), 'Bet Link': pd.Series(dtype='str')})

        for match in matchDf:
            time.sleep(np.abs(np.random.normal(delay, delay/2)))
            matchBetDf = pd.DataFrame({'MatchID': pd.Series(dtype='str'), 'Team A': pd.Series(dtype='str'), 'Team B': pd.Series(dtype='str'), 'Bet Return A': pd.Series(dtype='float'), 'Bet Return B': pd.Series(dtype='float'), 'Bet Website': pd.Series(dtype='str'), 'Bet Link': pd.Series(dtype='str')})

            MatchID = match['MatchID']
            page_data = requests.get(match['Match Link'])
            page_soup = BeautifulSoup(page_data.content, 'html.parser')
            print(f'🔵 [{MatchID}] {match['Team A']} vs {match['Team B']}')

            bet_items = page_soup.find_all('a', class_='wf-card mod-dark match-bet-item')
            for item in bet_items:
                betting_link = urljoin("https://www.vlr.gg", item.get('href'))
                # Extracting betting site name from Image
                img_tag = item.find('img')
                betting_site = img_tag['src'].split('/')[-1].split('.')[0] if img_tag else 'Unknown'
                teamA = match['Team A']
                teamB = match['Team B']
                halves = item.find_all('div', class_='match-bet-item-half')
                pending = True if item.find('div', class_='mod-pending') else False
                if len(halves) == 2 and not pending:
                    try:
                        # First half (Team 1)
                        teamA_info = halves[0].find('div', style=True)
                        teamA_odds = float(teamA_info.find(lambda tag: tag.name == "span" and "match-bet-item-odds" in tag.get("class", []) and "mod-1" in tag.get("class", [])).text.strip())
                        
                        # Second half (Team 2)
                        teamB_info = halves[1].find('div', style=True)
                        teamB_odds = float(teamB_info.find(lambda tag: tag.name == "span" and "match-bet-item-odds" in tag.get("class", []) and "mod-2" in tag.get("class", [])).text.strip())
                    except Exception as err:
                        print(f'Error parsing {betting_site} - {teamA} vs {teamB}: {err}')
                        break
                    print(f'{betting_site} - {teamA_odds} - {teamB_odds} @ {betting_link}')
                
                    tempDf = pd.DataFrame({'MatchID': [MatchID], 'Team A': [teamA], 'Team B': [teamB], 'Bet Return A': [teamA_odds], 'Bet Return B': [teamB_odds], 'Bet Website': [betting_site], 'Bet Link': [betting_link]})
                    
                    matchBetDf = pd.concat([matchBetDf, tempDf], ignore_index=True)
                
            if len(matchBetDf) > 0:
                # Append to main DataFrame
                betDf = pd.concat([betDf, matchBetDf], ignore_index=True)
                
        betDf['Bet Type'] = 'Match'
        betDf['Data Datetime'] = pd.Timestamp.now()
        betDf['Data Source'] = 'VLR.gg'
        return betDf
        

