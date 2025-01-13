from pixelprofit import *
import tabulate
import asyncio
import discord
import os
from dotenv import load_dotenv

from discord.ext import commands
from discord import app_commands

load_dotenv()
pagination_tracker = {}

# Setting up Pixel Profit
valorant = vlr_engine()

# Set up the bot
intents = discord.Intents.default()
intents.messages = True  # Ensure the bot can read messages
intents.reactions = True  # Ensure the bot can add reactions
intents.message_content = True  # Allow bot to read message content
bot = commands.Bot(command_prefix='!', intents=intents)

# Replace with your bot's token
TOKEN = os.getenv('BOT_TOKEN')

# Replace with the ID of the specific channel
SPECIFIC_CHANNEL_ID = os.getenv('CHANNEL_ID')

# Phrase to react to
TRIGGER_PHRASE = "Hello bot!"

# Event for when the bot is ready
@bot.event
async def on_ready():
    print(f'Bot is online! Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print('synced:', synced)
    except Exception as e:
        print('An error occurred while syncing commands:', e)
        
    try:
        valorant.update_matches()
    except Exception as e:
        print('An error occurred while updating matches:', e)

# In the case that the bot command is not found
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"Unknown command: `{ctx.message.content}`. Type `!help` to see the available commands.")
    else:
        # Handle other command-related errors if needed
        print(f"An error occurred: {error}")

@bot.tree.command(name='update')
@app_commands.describe(type="Update matches or odds")
async def update(interaction: discord.Interaction, type: str, game: str='valorant'):
    if type == "matches":
        updated_matches = valorant.update_matches()
        await interaction.response.defer()
        embed = discord.Embed(title=f"**VALORANT** Upcoming Matches", color=0x03f8fc, timestamp=interaction.created_at)
        updated_matches = updated_matches.sort_values(by='Datetime').head(5)
        state = 0
        for row in updated_matches.iterrows():
            match = row[1]
            embed.add_field(name=f"{match['Event Series']}", value=f"{match['Event']}\n{match['Datetime']}\n[{match['Team A']} vs {match['Team B']}\n]({match['Match Link']})", inline=False)
        embed.set_footer(text=f"Showing matches {0} to {min(5, valorant.get_matches().shape[0])} of {valorant.get_matches().shape[0]}")
        await asyncio.sleep(5)
        msg = await interaction.followup.send(embed = embed)
        pagination_tracker[msg.id] = state
        await msg.add_reaction('⬅️')
        await msg.add_reaction('➡️')
        
        def check(reaction, user):
            return (
                reaction.message.id == msg.id and
                (str(reaction.emoji) == "⬅️" or str(reaction.emoji) == "➡️") and
                user != bot.user  # Ensure the bot's own reactions are ignored
            )
        
        timeout = 30
        # Handling Pagination Buttons
        while True:
            try:
                reaction, user = await bot.wait_for("reaction_add", timeout=timeout, check=check)
                timeout = 30
                message = reaction.message
                if message.id not in pagination_tracker:
                    return
                
                state = pagination_tracker[message.id]
                if reaction.emoji == '⬅️':
                    print('left')
                    state = max(0, state - 5)
                elif reaction.emoji == '➡️':
                    print('right')
                    if state + 5 > valorant.get_matches().shape[0]:
                        await msg.remove_reaction(reaction.emoji, user)
                        return
                    state = max(0, state + 5)
                else:
                    return
                
                embed = discord.Embed(title=f"**VALORANT** Upcoming Matches", color=0x03f8fc,timestamp=interaction.created_at)
                updated_matches = valorant.get_matches().sort_values(by='Datetime').iloc[state:min(state + 5, valorant.get_matches().shape[0])]
                print(updated_matches)
                for row in updated_matches.iterrows():
                    match = row[1]
                    embed.add_field(name=f"{match['Event Series']}", value=f"{match['Event']}\n{match['Datetime']}\n[{match['Team A']} vs {match['Team B']}]({match['Match Link']})", inline=False)
                embed.set_footer(text=f"Showing matches {state} to {min(state + 5, valorant.get_matches().shape[0])} of {valorant.get_matches().shape[0]}")
                await msg.edit(embed=embed)
                await msg.remove_reaction(reaction.emoji, user)
                
                pagination_tracker[message.id] = state
            except TimeoutError:
                break
    elif type == "odds":
        updated_odds = valorant.update_odds()
        await interaction.response.send_message(f"Updated odds for {game}!")


# Helper function to generate match embeds
def generate_match_embed(matches, state):
    embed = discord.Embed(title=f"**VALORANT** Upcoming Matches", color=0x03f8fc)
    updated_matches = matches.sort_values(by='Datetime').iloc[state:min(state + 5, matches.shape[0])]
    for row in updated_matches.iterrows():
        match = row[1]
        embed.add_field(name=f"{match['Event Series']}", value=f"{match['Event']}\n{match['Datetime']}\n[{match['Team A']} vs {match['Team B']}]({match['Match Link']})", inline=False)
    embed.set_footer(text=f"Showing matches {state} to {min(state + 5, matches.shape[0])} of {matches.shape[0]}")
    return embed

@bot.tree.command(name="show")
@app_commands.describe(type="Show matches or odds")
async def show(interaction: discord.Interaction, type: str, game: str='valorant'):
    if type == "matches":
        updated_matches = valorant.get_matches()
    
        embed = generate_match_embed(updated_matches, 0)
        await interaction.response.send_message(embed = embed)
        msg = await interaction.original_response()
        pagination_tracker[msg.id] = 0
        await msg.add_reaction('⬅️')
        await msg.add_reaction('➡️')
        
        def check(reaction, user):
            return (
                reaction.message.id == msg.id and
                (str(reaction.emoji) == "⬅️" or str(reaction.emoji) == "➡️") and
                user != bot.user  # Ensure the bot's own reactions are ignored
            )
        
        timeout = 30
        # Handling Pagination Buttons
        while True:
            try:
                reaction, user = await bot.wait_for("reaction_add", timeout=timeout, check=check)
                timeout = 30
                message = reaction.message
                if message.id not in pagination_tracker:
                    return
                
                state = pagination_tracker[message.id]
                if reaction.emoji == '⬅️':
                    print('left')
                    state = max(0, state - 5)
                elif reaction.emoji == '➡️':
                    print('right')
                    if state + 5 > valorant.get_matches().shape[0]:
                        await msg.remove_reaction(reaction.emoji, user)
                        continue
                    state = max(0, state + 5)
                else:
                    return
                
                embed = generate_match_embed(updated_matches, state)
                await msg.edit(embed=embed)
                await msg.remove_reaction(reaction.emoji, user)
                
                pagination_tracker[message.id] = state
            except TimeoutError:
                break
    elif type == "odds":
        updated_odds = valorant.get_odds()
        await interaction.response.send_message(f"Showing odds for {game}!")
    
    
    

    
# MESSAGE HANDLING
@bot.event
async def on_message(message):
    # Avoid the bot responding to itself
    if message.author == bot.user:
        return

    # Check for the specific phrase
    if message.content == TRIGGER_PHRASE:
        # Add a reaction to the message (using emoji)
        await message.add_reaction('👋')  # Wave emoji
        await message.channel.send('Hello! 👋')  # Bot's reply
        print('Trigger phrase detected!')
    
    # Allow the bot to process commands
    await bot.process_commands(message)


# Run the bot
bot.run(TOKEN)
