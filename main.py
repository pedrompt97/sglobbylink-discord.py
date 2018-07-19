# sglobbylink-discord.py
# by Mr Peck (2018)
# project page: https://github.com/itsmrpeck/sglobbylink-discord.py
# 
# NOTE: You must enter your Discord bot token and Steam API key in the SETTINGS section below, or the bot won't work!

import discord
import asyncio
import urllib.request
import json
import threading
from enum import Enum

versionNumber = "1.1"

######################################
####### SETTINGS:

# IMPORTANT: get your Discord bot token from https://discordapp.com/developers/applications/me
discordBotTokenIMPORTANT = "PASTE_DISCORD_BOT_TOKEN_HERE"

# IMPORTANT: get your Steam API key from https://steamcommunity.com/dev/apikey
steamApiKeyIMPORTANT = "PASTE_STEAM_WEB_API_KEY_HERE"

# You can replace this with whatever you want! This is where the bot stores its users' Steam IDs.
steamIdFileName = "steam_ids.txt"

# Add channel names to the whitelist if you only want the bot to read and reply to messages in certain channels.
# Leaving the list empty means the bot runs in all channels of your server.
# Don't include the '#' at the start of the channel names!
# e.g. channelWhitelist = ["skullgirls", "guilty-gear"]
channelWhitelist = []

# Rate limiting: each user can only ask the bot for this many things per day. This stops you from breaking the daily request limit for your Steam API key.
maxDailyRequestsPerUser = 60

#######
######################################




client = discord.Client()

steamIdTable = {}

steamIdInstructions = "enter your full Steam profile URL or just the last part, e.g. `!steamid http://steamcommunity.com/id/robinwalker/` or `!steamid robinwalker`"


todaysRequestCounts = {}

requestCountsLock = threading.RLock()

class RequestLimitResult(Enum):
    LIMIT_NOT_REACHED = 1
    LIMIT_JUST_REACHED = 2
    ALREADY_OVER_LIMIT = 3

def save_steam_ids():
    try:
        with open(steamIdFileName, 'w+') as f:
            for steamId in steamIdTable.keys():
                f.write(steamId + " " + steamIdTable[steamId] + "\n")
    except:
        pass

def load_steam_ids():
    try:
        with open(steamIdFileName, 'r') as f:
            steamIdTable.clear()
            for line in f:
                line = line.rstrip('\n')
                splitLine = line.split(" ")
                if len(splitLine) >= 2:
                    steamIdTable[splitLine[0]] = splitLine[1]
    except:
        pass

def increment_request_count(userIdStr): # returns whether or not the user has hit their daily request limit
    if maxDailyRequestsPerUser <= 0:
        return RequestLimitResult.ALREADY_OVER_LIMIT

    with requestCountsLock:

        if userIdStr not in todaysRequestCounts.keys():
            todaysRequestCounts[userIdStr] = 0

        if todaysRequestCounts[userIdStr] > maxDailyRequestsPerUser:
            return RequestLimitResult.ALREADY_OVER_LIMIT

        elif todaysRequestCounts[userIdStr] == maxDailyRequestsPerUser:
            todaysRequestCounts[userIdStr] += 1
            return RequestLimitResult.LIMIT_JUST_REACHED

        else:
            todaysRequestCounts[userIdStr] += 1
            return RequestLimitResult.LIMIT_NOT_REACHED

    return RequestLimitResult.ALREADY_OVER_LIMIT


async def clear_request_counts_once_per_day():
    await client.wait_until_ready()
    while not client.is_closed:
        with requestCountsLock:
            todaysRequestCounts.clear()
        await asyncio.sleep(60*60*24) # task runs every 24 hours
        


@client.event
async def on_ready():
    load_steam_ids()
    client.loop.create_task(clear_request_counts_once_per_day())

@client.event
async def on_message(message):

    # ignore messages not on the whitelisted channel
    if channelWhitelist:
        if not message.channel:
            return # ignore all Direct Messages

        channelFound = False
        for channelName in channelWhitelist:
            if channelName == message.channel.name:
                channelFound = True
                break
        if not channelFound:
            return


    if message.content.startswith('!help'):
        # rate limit check
        rateLimitResult = increment_request_count(message.author.id)
        if rateLimitResult == RequestLimitResult.ALREADY_OVER_LIMIT:
            return
        elif rateLimitResult == RequestLimitResult.LIMIT_JUST_REACHED:
            await client.send_message(message.channel, "Error: Daily request limit reached for user " + message.author.name + ". Try again in 24 hours.")
            return

        await client.send_message(message.channel, "Hello, I am sglobbylink-discord.py v" + versionNumber + " by Mr Peck.\n\nCommands:\n- `!lobby`: posts the link to your current Steam lobby.\n- `!steamid`: tells the bot what your Steam profile is. You can " + steamIdInstructions)

    elif message.content.startswith('!steamid'):

        # rate limit check
        rateLimitResult = increment_request_count(message.author.id)
        if rateLimitResult == RequestLimitResult.ALREADY_OVER_LIMIT:
            return
        elif rateLimitResult == RequestLimitResult.LIMIT_JUST_REACHED:
            await client.send_message(message.channel, "Error: Daily request limit reached for user " + message.author.name + ". Try again in 24 hours.")
            return

        words = message.content.split(" ")
        if len(words) < 2:
            await client.send_message(message.channel, "`!steamid` usage: " + steamIdInstructions)
        else:
            idStr = words[1]
            idStr = idStr.rstrip('/')

            if idStr.find("steamcommunity.com") != -1:
                lastSlash = idStr.rfind('/')
                if lastSlash != -1:
                    idStr = idStr[lastSlash + 1:]

            if len(idStr) > 200:
                await client.send_message(message.channel, "Error: Steam ID too long.")
            elif idStr.isdigit():
                steamIdTable[message.author.id] = idStr
                save_steam_ids()
                await client.send_message(message.channel, "Saved " + message.author.name + "'s Steam ID.")
            else:
                steamIdUrl = "http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/?key=" + steamApiKeyIMPORTANT + "&vanityurl=" + idStr
                contents = urllib.request.urlopen(steamIdUrl).read()
                if contents:
                    data = json.loads(contents)
                    if data["response"] is None:
                        await client.send_message(message.channel, "SteamAPI: ResolveVanityURL() failed for " + message.author.name + ". Is Steam down?")
                    else:
                        if "steamid" in data["response"].keys():
                            steamIdTable[message.author.id] = data["response"]["steamid"]
                            save_steam_ids()
                            await client.send_message(message.channel, "Saved " + message.author.name + "'s Steam ID.")
                        else:
                            await client.send_message(message.channel, "Could not find Steam ID: " + idStr + ". Make sure you " + steamIdInstructions)
                else:
                    await client.send_message(message.channel, "Error: failed to find " + message.author.name + "'s Steam ID.")

    elif message.content.startswith('!lobby'):
        if message.author.id in steamIdTable.keys():

            # rate limit check
            rateLimitResult = increment_request_count(message.author.id)
            if rateLimitResult == RequestLimitResult.ALREADY_OVER_LIMIT:
                return
            elif rateLimitResult == RequestLimitResult.LIMIT_JUST_REACHED:
                await client.send_message(message.channel, "Error: Daily request limit reached for user " + message.author.name + ". Try again tomorrow.")
                return

            steamId = steamIdTable[message.author.id]
            profileUrl = "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=" + steamApiKeyIMPORTANT + "&steamids=" + steamId
            contents = urllib.request.urlopen(profileUrl).read()
            if contents:
                data = json.loads(contents)
                if "response" in data.keys():
                    pdata = data["response"]["players"][0]
                    if "lobbysteamid" in pdata.keys():
                        steamLobbyUrl = "steam://joinlobby/" + pdata["gameid"] + "/" + pdata["lobbysteamid"] + "/" + steamId
                        gameName = ""
                        if "gameextrainfo" in pdata.keys():
                            gameName = pdata["gameextrainfo"] + " "
                        await client.send_message(message.channel, message.author.name + "'s " + gameName + "lobby: " + steamLobbyUrl)
                    else:
                        await client.send_message(message.channel, "Lobby not found for " + message.author.name + ". Is your Steam profile public (including Game Details), and are you in a lobby? If this is your first time using the bot, make sure your !steamid is set to your Steam profile URL.")
                else:
                    await client.send_message(message.channel, "SteamAPI: GetPlayerSummaries() failed for " + message.author.name + ". Is Steam down?")
                        
            else:
                await client.send_message(message.channel, "SteamAPI: GetPlayerSummaries() failed for " + message.author.name + ". Is Steam down?")
        else:
            await client.send_message(message.channel, "Steam ID not found for " + message.author.name +  ". Type `!steamid` and " + steamIdInstructions)

client.run(discordBotTokenIMPORTANT)
