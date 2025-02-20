from urllib.parse import urljoin, urlparse
from datetime import datetime as dt
from bs4 import BeautifulSoup
import requests
import pandas as pd
import numpy as np
import textwrap
import re

from .utils.extractor import extractor

class vlr_engine():
    def __init__(self):
        # Initializing Event Dataframe
        self._eventDf = pd.DataFrame({'Datetime': pd.Series(dtype="datetime64[ns]"), 'Event Series': pd.Series(dtype='str'), 'Event': pd.Series(dtype='str'), 'Team A': pd.Series(dtype='str'), 'Team B': pd.Series(dtype='str'), 'Match Link': pd.Series(dtype='str')})
        self._eventDf.index.name = "MatchID"
        
        # Initializing Odds Dataframe
        self._oddsDf = pd.DataFrame({'MatchID': pd.Series(dtype='str'), 'Team A': pd.Series(dtype='str'), 'Team B': pd.Series(dtype='str'), 'Bet Type': pd.Series(dtype='str'), 'Bet Return A': pd.Series(dtype='float'), 'Bet Return B': pd.Series(dtype='float'), 'Bet Website': pd.Series(dtype='str'), 'Bet Link': pd.Series(dtype='str')})
        self._oddsDf.index.name = 'MatchID'
        
        # Initializing Arbitrage Dataframe
        self._arbDf = pd.DataFrame()
        self._arbDf.index.name = 'MatchID'
        
        self.extractor = extractor()
    
    # Update the matches dataframe
    def update_matches(self, include_tbd=False, include_running=False):
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
    
    # Returns existing matches dataframe
    def get_matches(self):
        return self._eventDf
    
    # Update the odds dataframe
    def update_odds(self):
        #self._oddsDf = pd.read_csv('odds.csv')
        self._oddsDf = self.extractor.get_all(self._eventDf)
        #self._oddsDf.to_csv('odds.csv', index=False)
        print("🟢 Updated and saved Odds dataframe.")
    
    # Returns existing odds dataframe
    def get_odds(self):
        return self._oddsDf
    
    def update_arbs(self):
        self._arbDf = pd.DataFrame()
        self._arbDf.index.name = 'MatchID'
        match_list = list(set(self._oddsDf['MatchID'].to_list()))
        type_list = list(set(self._oddsDf['Bet Type'].to_list()))
        for betType in type_list:
            for matchID in match_list:
                tempDf = self._oddsDf[(self._oddsDf['MatchID'] == matchID) & (self._oddsDf['Bet Type'] == betType)]
                # Get Max of column Bet Return A
                if tempDf.empty:
                    continue
                maxARow = tempDf.sort_values('Bet Return A', ascending=False).iloc[0]
                # Get Max of column Bet Return B
                maxBRow = tempDf.sort_values('Bet Return B', ascending=False).iloc[0]
                
                composite = (1/maxARow["Bet Return A"] + 1/maxBRow["Bet Return B"]) * 100
                print(f'[{matchID}] {maxARow["Team A"]} vs {maxBRow["Team B"]} ({betType})')
                print(f'Best Odds: {maxARow["Bet Return A"]:.3f} vs {maxBRow["Bet Return B"]:.3f} ({maxARow["Bet Website"]} vs {maxBRow["Bet Website"]})')
                print(f'Composite Percentage: {composite:.2f}%')
                tempDf = pd.DataFrame({'MatchID': [matchID], 'Team A': [maxARow["Team A"]], 'Team B': [maxBRow["Team B"]], 'Bet Type': [betType], 'Best Return A': [maxARow["Bet Return A"]], 'Best Return B': [maxBRow["Bet Return B"]], 'Best Site A': [maxARow["Bet Website"]], 'Best Site B': [maxBRow["Bet Website"]], 'Composite Percentage': [composite], 'Site A Link': [maxARow["Bet Link"]], 'Site B Link': [maxBRow["Bet Link"]]})
                self._arbDf = pd.concat([self._arbDf, tempDf], ignore_index=True)
                if composite < 100:
                    teamARatio = 1/maxARow["Bet Return A"] * composite
                    teamBRatio = 1/maxBRow["Bet Return B"] * composite
                    print(f'Betting Site A ({maxARow["Bet Website"]}): {teamARatio:.2f} ({maxARow["Bet Link"]})')
                    print(f'Betting Site B ({maxBRow["Bet Website"]}): {teamBRatio:.2f} ({maxBRow["Bet Link"]})')
                    print(f'🟢 Arbitrage Opportunity! Ratio {teamARatio:.2f}:{teamBRatio:.2f} -> {100-composite:.2f}')
                else:
                    print('🔴 No Arbitrage Opportunity...')
        # Using index of arbDf, get the match Datetime from matchDf
        #self._arbDf.to_csv('arbs.csv', index=False)
        self._arbDf = self._arbDf.join(self._eventDf[['Datetime', 'Match Link']], on='MatchID')
        return self._arbDf
    
    def get_arbs(self):
        return self._arbDf
    
    def __del__(self):
        del self.extractor

            