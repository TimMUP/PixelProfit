from urllib.parse import urljoin, urlparse
from datetime import datetime as dt
from bs4 import BeautifulSoup
import requests
import pandas as pd
import numpy as np
import re

from .utils.extractor import extractor

class vlr_engine():
    def __init__(self):
        self._eventDf = None    # Event Data Dataframe
        self._oddsDf = None     # Odds and Sources Dataframe
        self._oppDf = None      # Consolidated Best Oppourtunities 
        self.extractor = extractor()
        
    def update_matches(self, include_tbd=False, include_running=False):
        self._eventDf = pd.DataFrame({'Datetime': pd.Series(dtype="datetime64[ns]"), 'Event Series': pd.Series(dtype='str'), 'Event': pd.Series(dtype='str'), 'Team A': pd.Series(dtype='str'), 'Team B': pd.Series(dtype='str'), 'Match Link': pd.Series(dtype='str')})
        self._eventDf.index.name = "MatchID"
        page_count = 1
        while True:
            target_url = f"https://www.vlr.gg/matches/?page={page_count}"
            page_data = requests.get(target_url)
            page_soup = BeautifulSoup(page_data.content, 'html.parser')
            
            date_cards = page_soup.find_all('div', class_='wf-label mod-large')
            game_cards = page_soup.find_all(lambda tag: tag.name == 'div' and tag.get('class') == ['wf-card'])
            
            if len(date_cards) == 0:
                break
            
            for dateCard, gameCard in zip(date_cards, game_cards):
                dtStr = dateCard.find(string=True).strip()
                dtObj = dt.strptime(dtStr, '%a, %B %d, %Y')
                print('dtObj:', dtObj)
                
                for gameItem in gameCard.find_all('a', class_='wf-module-item'):
                    gameTimeStr = gameItem.find('div', class_='match-item-time').find(string=True).strip()
                    gameTimeObj = dt(1, 1, 1, 0, 0, 0) if gameTimeStr == '' else dt.strptime(gameTimeStr, '%I:%M %p') 
                    gameDtObj = dt(dtObj.year, dtObj.month, dtObj.day, gameTimeObj.hour, gameTimeObj.minute)
                    print(gameDtObj)
                    
                    gameTeamNames = gameItem.find_all('div', class_='match-item-vs-team-name')
                    teamAName = gameTeamNames[0].text.strip()
                    teamBName = gameTeamNames[1].text.strip()
                    print(f"\'{teamAName}\' vs \'{teamBName}\'")
                    
                    eventName = gameItem.find('div', class_='match-item-event-series').text.strip()
                    eventSeries = gameItem.find('div', class_='match-item-event').find_all(string=True)[-1].strip()
                    print(f"\'{eventName}\' @ \'{eventSeries}\'")
                    
                    matchLink = f"{urljoin("https://www.vlr.gg", gameItem.get('href'))}"
                    matchID = urlparse(matchLink).path.split('/')[-2]
                    print(f"\'{matchID}\'")
                    
                    self._eventDf.loc[matchID] = [gameDtObj, eventSeries, eventName, teamAName, teamBName, matchLink]
                
            page_count += 1
        
        # Filter out everywhere team names are 'TBD'
        if not include_tbd:
            self._eventDf = self._eventDf[(self._eventDf['Team A'] != 'TBD') & (self._eventDf['Team B'] != 'TBD')]
            
        # Filter out currently running matches
        if not include_running:
            self._eventDf = self._eventDf[self._eventDf['Datetime'] > dt.now()]

        return self._eventDf
    
    def get_matches(self):
        return self._eventDf
    
    def update_odds(self):
        self._oddsDf = self.extractor.get_all(self._eventDf)
        
    def get_odds(self):
        return self._oddsDf
    
    def __del__(self):
        del self.extractor

            