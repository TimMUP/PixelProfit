from pixelprofit import *
from dotenv import load_dotenv

from discord.ext import commands
from discord import app_commands

load_dotenv()
pagination_tracker = {}
valorant = vlr_engine()

valorant.update_matches()
valorant.update_odds()
valorant.update_arbs()

valorant.get_arbs().to_csv('arbs.csv', index=False)
valorant.get_odds().to_csv('odds.csv', index=False)


