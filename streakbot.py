import discord
from discord.ext import commands
from discord.ext import tasks
from datetime import datetime
from database import DataBase
import dbl
from discord.ext.commands import MissingPermissions
from discord.ext.commands import CommandError

bot = commands.Bot(command_prefix='!')


class StreakBot(commands.Cog, command_attrs=dict(hidden=False, brief="Normal User", help="I'm a mysterious command.")):
    today = datetime.today().date().strftime("%d-%m-%Y")
    yesterday = None

    def __init__(self, bot_client):
        self.bot = bot_client
        self.bot.remove_command("help")
        self.embed = None
        self.token = ""
        self.dblpy = dbl.DBLClient(self.bot, self.token,
                                   autopost=True)  # Auto post will post your guild count every 30 minutes

        self.dataBase = DataBase('discordStreakBot.db')

        # self.dataBase.createTable()
        # self.dataBase.createGlobalTable()

    async def change_profile_picture(self):
        with open('snapchat.png', 'rb') as f:
            await self.bot.user.edit(avatar=f.read())

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'We have logged in as {self.bot.user}\n')
        self.dateCheck.start()
        #self.scanCurrentServer()

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, CommandError):
            return
        raise error

    async def on_guild_post(self):
        print("Server count posted successfully")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        channel_guild_from = channel.guild
        channel_id = str(channel.id)

        server_channels_to_monitor = self.dataBase.get_server_channels(channel_guild_from)

        # if the server has set a specific channel to monitor prior
        if server_channels_to_monitor is not None:

            if channel_id in server_channels_to_monitor:
                # remove that channel provided
                self.dataBase.remove_server_channel(channel_guild_from, channel)

                print(f"{channel} was removed from database as it was deleted from the server")

    @commands.Cog.listener()
    async def on_voice_state_update(self, user, previous_voice_state, current_voice_state):

        user = user
        guild = user.guild

        # ignore any bot that would join voice channels
        if not user.bot:
            self.fillNoneData(guild, user)

            # check if the guild wants to track
            if self.dataBase.track_voice(guild):

                # check if the user has already streaked other wise ignore
                if not self.dataBase.checkUserStreaked(guild.id, user.id):

                    # if the user just recently joined a voice channel
                    joined_a_voice_channel = True if previous_voice_state.channel is None else False
                    user_left_voice_channel = True if current_voice_state.channel is None else False

                    user_current_mute_state = True if current_voice_state.mute or current_voice_state.self_mute else False

                    user_active_voice_time = self.dataBase.get_voice_status(guild, user)
                    # check if the channel the user has moved to is not an afk channel
                    if not current_voice_state.afk:
                        # check if they just recently joined a channel and is not in a muted state
                        if joined_a_voice_channel and not user_current_mute_state:
                            print(f"{user} has joined the voice channel: {current_voice_state.channel.name}")
                            self.dataBase.set_voice_join_time(guild, user)
                            return
                        # check if the user has left the voice call and not in a muted state as then we would update database
                        elif user_left_voice_channel and not user_current_mute_state:

                            # this is only there to check if there the  user was in an active call before hand
                            if user_active_voice_time != 0:
                                print(f"{user} has left the voice channel: {previous_voice_state.channel.name}")
                                self.dataBase.update_voice_time(guild, user)
                                return
                        # user has joined a voice channel but muted
                        elif joined_a_voice_channel and user_current_mute_state:
                            return
                        # user has left a voice channel but muted
                        elif user_left_voice_channel and user_current_mute_state:
                            return
                        # check if user has moved to a different voice channel
                        try:
                            moved_channel = True if previous_voice_state.channel.id != current_voice_state.channel.id else False

                        except AttributeError:
                            moved_channel = False

                        # will be used to check if the user is moving around the voice channel
                        if moved_channel:
                            # if user moved channel while muted ignore this
                            if user_current_mute_state:
                                print(f"{user} moved channel while muted")
                                return
                            else:
                                if previous_voice_state.afk:
                                    print(f"{user} has left afk channel")
                                    self.dataBase.set_voice_join_time(guild, user)
                                    return
                                else:
                                    # user moved channel un-muted
                                    print(f"{user} has moved channel un-muted")
                                    return
                        # if the user is currently muted
                        if user_current_mute_state:
                            # if the user was muted but was not in a call before (it's for user that joins a stream)
                            if user_active_voice_time != 0:
                                self.dataBase.update_voice_time(guild, user)
                                print(f"{user} has muted in: {current_voice_state.channel.name}")
                        else:
                            # if the user was  never muted but was not in a call before (it's for user that joins a stream)
                            if user_active_voice_time == 0 and current_voice_state.channel is not None:
                                print(f"{user} has un-muted in: {current_voice_state.channel.name}")
                                self.dataBase.set_voice_join_time(guild, user)

                    else:

                        if not previous_voice_state.afk and not user_current_mute_state:
                            if user_active_voice_time != 0:
                                print(f"{user} has been moved to afk")
                                self.dataBase.update_voice_time(guild, user)

    @commands.Cog.listener()
    async def on_message(self, message):

        user = message.author
        userID = user.id
        guildID = message.guild.id
        guild = message.guild

        # ignore bots
        if not user.bot:
            messageLength = len(message.content.split())
            channel_message_from = str(message.channel.id)

            self.fillNoneData(message.guild, user)

            # check if the user wants to track words
            if self.dataBase.track_word(guild):

                server_channels_to_monitor = self.dataBase.get_server_channels(guild)

                # if no channels were assigned then we track all the channels
                if server_channels_to_monitor is None or len(server_channels_to_monitor) == 0:


                    # all info are updated on the database such as streaking etc
                    self.dataBase.update_text_streak(guildID, userID, messageLength)

                # will be used to monitor specific channels

                elif channel_message_from in server_channels_to_monitor:
                
                    self.dataBase.update_text_streak(guildID, userID, messageLength)

            self.dataBase.update_word_streak_global(userID, messageLength)

    @commands.command(brief="Admin", help="``!voice enable`` Enable voice to be counted for streaking\n"
                                          "``!voice disable`` Disable voice to be counted for streaking\n"
                                          "``!voice threshold (amount) optional:(minute|hour)``\n"
                                          "Set the threshold for how long the user needs to be in call to gain a streak"
                                          "user's that are muted will not be counted to words tracking total time they were in the call")
    async def voice(self, ctx, *args):
        administrator = ctx.author.guild_permissions.administrator
        if administrator or ctx.author.id == 125604422007914497:
            if len(args) <= 4:

                guild = ctx.author.guild

                command = ' '.join(args)

                if command == "enable":

                    # check if the guild command has already been enabled otherwise enable it
                    if not self.dataBase.track_voice(guild):
                        self.dataBase.enable_track_voice(guild)
                        await ctx.channel.send("Voice channels will now be counted for streak!", delete_after=10)

                    else:
                        await ctx.channel.send("Voice channels are already counted for streak!", delete_after=10)

                # check if the guild command was already disabled other wise enable it
                elif command == "disable":
                    if self.dataBase.track_voice(guild):
                        self.dataBase.disable_track_voice(guild)
                        await ctx.channel.send("Voice channels will not be counted for streak!", delete_after=10)
                    else:
                        await ctx.channel.send("Voice channels are already disabled for streak!", delete_after=10)

                # will be used to track the
                elif 'threshold' in command:

                    # unpack the threshold amount to be set
                    command, threshold_amount, *other_arguments = args

                    if self.dataBase.track_voice(guild):

                        # try convert the given digit into
                        try:
                            threshold_amount = int(threshold_amount)

                        except ValueError:

                            await ctx.channel.send("Invalid digit sent")

                        # if no other arguments were passed in (minutes | hours)
                        if not other_arguments:

                            if threshold_amount > 86400:
                                await ctx.channel.send("86400 seconds is the max!",
                                                       delete_after=10)
                                self.dataBase.set_voice_guild_threshold(guild, 86400)

                                await ctx.channel.send(
                                    f"New voice threshold has been set to {86400:0,} seconds for {guild.name}\n",
                                    delete_after=10)

                            else:

                                self.dataBase.set_voice_guild_threshold(guild, threshold_amount)

                                await ctx.channel.send(
                                    f"New voice threshold has been set to {threshold_amount:0,} seconds for {guild.name}\n",
                                    delete_after=10)

                        # if the user has given minutes argument convert it to seconds then update database
                        elif other_arguments[0].startswith('minute'):

                            convert_threshold_amount = threshold_amount * 60

                            if convert_threshold_amount > 1440:
                                await ctx.channel.send("1440 minutes is the max!",
                                                       delete_after=10)
                                self.dataBase.set_voice_guild_threshold(guild, 1440)

                                await ctx.channel.send(
                                    f"New voice threshold has been set to {1440:0,} minute for {guild.name}\n",
                                    delete_after=10)

                            else:
                                self.dataBase.set_voice_guild_threshold(guild, convert_threshold_amount)

                                await ctx.channel.send(
                                    f"New voice threshold has been set to {threshold_amount:0,} minute for {guild.name}\n",
                                    delete_after=10)

                        # if the user has given hour argument convert it to seconds then update database
                        elif other_arguments[0].startswith('hour'):

                            convert_threshold_amount = (threshold_amount * 60) * 60

                            if convert_threshold_amount > 24:
                                await ctx.channel.send("24 hours is the max!",
                                                       delete_after=10)
                                self.dataBase.set_voice_guild_threshold(guild, 24)

                                await ctx.channel.send(
                                    f"New voice threshold has been set to {24:0,} hour for {guild.name}\n",
                                    delete_after=10)

                            else:
                                self.dataBase.set_voice_guild_threshold(guild, convert_threshold_amount)

                                await ctx.channel.send(
                                    f"New voice threshold has been set to {threshold_amount:0,} hour for {guild.name}\n",
                                    delete_after=10)
                    else:
                        await ctx.channel.send(
                            'Please enable voice to be counted for streaks before you can set threshold. !voice enable',
                            delete_after=10)

    @commands.command(brief="Admin", help="``!word enable `` Enable words to be counted for streaking\n"
                                          "``!word disable`` Disable words to be counted for streaking\n"
                                          "``!word threshold (amount) Set the minimum number of words for a server member to get a streak.``\n"
                      )
    async def word(self, ctx, *args):
        administrator = ctx.author.guild_permissions.administrator
        if administrator or ctx.author.id == 125604422007914497:
            if len(args) <= 4:

                guild = ctx.author.guild

                command = ' '.join(args)

                if command == "enable":

                    # check if the guild command has already been enabled otherwise enable it
                    if not self.dataBase.track_word(guild):

                        self.dataBase.enable_track_word(guild)
                        await ctx.channel.send("Words will now be counted for streak!")

                    else:
                        await ctx.channel.send("Words are already counted for streak!")

                # check if the guild command was already disabled other wise enable it
                elif command == "disable":
                    if self.dataBase.track_word(guild):
                        self.dataBase.disable_track_word(guild)
                        await ctx.channel.send("Words will not be counted for streak!")
                    else:
                        await ctx.channel.send("Words are already disabled for streak!")

                # will be used to track the
                elif 'threshold' in command:

                    # unpack the threshold amount to be set
                    command, threshold_amount = args

                    # try convert the given digit into
                    try:
                        threshold_amount = int(threshold_amount)

                        if self.dataBase.track_word(guild):
                            self.dataBase.setServerThreshold(guild.id, threshold_amount)
                            await ctx.channel.send(
                                f"New message threshold has been set for the server to {threshold_amount:0,}")

                        else:
                            await ctx.channel.send(
                                'Please enable words to be counted for streaks before you can set threshold. !word enable',
                                delete_after=10)

                    except ValueError:
                        await ctx.channel.send("Invalid digit sent. Example - !word threshold 500", delete_after=10)

    @commands.command(brief="Admin",
                      help="``!add <#channel_name> `` add a text-channel for monitoring. You can add up to 3 text-channel per command by doing the following "
                           "``!add <#channel_name> <#channel_name> <#channel_name>``")
    async def add(self, ctx):

        # only need first 3
        channel_mentioned = ctx.message.channel_mentions[:3]
        guild = ctx.guild
        administrator = ctx.author.guild_permissions.administrator
        if administrator or ctx.author.id == 125604422007914497:
            check_words_is_tracked = self.dataBase.track_word(guild)

            if check_words_is_tracked:
                server_channels_to_monitor = self.dataBase.get_server_channels(guild)

                # if the server has set a specific channel to monitor prior
                if server_channels_to_monitor is not None:

                    if not channel_mentioned:
                        await ctx.channel.send("Specify a text-channel to add. ``!add <#channel_name>``")

                    else:
                        channel_names = []
                        channel_exist = []

                        # loop through the channels mentioned
                        for channel in channel_mentioned:

                            # check if the channel id exist on database
                            if str(channel.id) in server_channels_to_monitor:
                                channel_exist.append(f"``#{channel.name}``")

                            else:
                                channel_names.append(f"``#{channel.name}``")
                                self.dataBase.add_server_channel(guild, channel)

                        filtered_channel_names = " and ".join(channel_exist)
                        filtered_channel_addition = " and ".join(channel_names)

                        if len(filtered_channel_names) > 0:
                            await ctx.channel.send(
                                f"{filtered_channel_names} {'are' if len(channel_exist) > 1 else 'is'} already tracked for streaking!")

                        if len(filtered_channel_addition) > 0:
                            await ctx.channel.send(
                                f"{filtered_channel_addition} {'are' if len(channel_names) > 1 else 'is'} now been tracked for streaking!")

                else:
                    channel_names = []
                    # loop through the channels mentioned
                    for channel in channel_mentioned:
                        channel_names.append(f"``#{channel.name}``")
                        self.dataBase.add_server_channel(guild, channel)

                    filtered_channel_names = " and ".join(channel_names)
                    await ctx.channel.send(
                        f"{filtered_channel_names} {'are' if len(channel_names) > 1 else 'is'} now been tracked for streaking!")
            else:
                await ctx.channel.send("Enable words to be tracked first! ``!word enable``")

    @commands.command(brief="Admin",
                      help="``!remove <#channel_name>`` remove a text-channel for monitoring. You can remove up to 3 text-channel per command by doing the following "
                           "``!remove <#channel_name> <#channel_name> <#channel_name>``")
    async def remove(self, ctx):

        # only need first 3
        channel_mentioned = ctx.message.channel_mentions[:3]
        guild = ctx.guild
        administrator = ctx.author.guild_permissions.administrator

        if administrator or ctx.author.id == 125604422007914497:

            check_words_is_tracked = self.dataBase.track_word(guild)

            if check_words_is_tracked:

                server_channels_to_monitor = self.dataBase.get_server_channels(guild)

                # if the server has set a specific channel to monitor prior
                if server_channels_to_monitor is not None:

                    if not channel_mentioned:
                        await ctx.channel.send("Specify a text-channel to remove. ``!remove <#channel_name>``")

                    else:
                        channel_names = []
                        channel_not_exist = []
                        # loop through the channels mentioned
                        for channel in channel_mentioned:
                            # check if the channel id exist on database
                            if str(channel.id) in server_channels_to_monitor:

                                # if it does append to channel_names to be used to send to channel
                                channel_names.append(f"``#{channel.name}``")

                                # remove that channel provided
                                self.dataBase.remove_server_channel(guild, channel)

                            else:
                                channel_not_exist.append(f"``#{channel.name}``")

                        filtered_channel_names = " and ".join(channel_names)
                        filtered_channel_not_exist = " and ".join(channel_not_exist)

                        if len(filtered_channel_names) > 0:
                            await ctx.channel.send(
                                f"{filtered_channel_names} {'are' if len(channel_names) > 1 else 'is'} removed for streaking!")

                        if len(filtered_channel_not_exist) > 0:
                            await ctx.channel.send(
                                f"{filtered_channel_not_exist}  {'do not' if len(channel_not_exist) > 1 else 'does'} exist on the streaking database")

                else:
                    await ctx.channel.send(
                        "You need to setup a specific channel for me to monitor first, !add <#channel_name>",
                        delete_after=10)
            else:
                await ctx.channel.send("Enable words to be tracked first! ``!word enable``")

    @commands.command(brief="Admin", help="The current configuration for this server")
    async def settings(self, ctx):
        administrator = ctx.author.guild_permissions.administrator

        guild = ctx.guild

        guild_id = guild.id

        if administrator or ctx.author.id == 125604422007914497:
            # how many members the guild has
            totalUsers = len(guild.members)

            totalChannels = len(guild.channels)

            server_channels_monitor = self.dataBase.get_server_channels(guild)
            # check if any server exist
            if server_channels_monitor is None or len(server_channels_monitor) == 0:
                channels_monitored = ":small_blue_diamond: All Text-channels are monitored.\n" \
                                     ":small_blue_diamond:``!add <#channel_name>`` customise the channels to monitor "

            else:
                channels_monitored = " ".join(
                    [f":small_blue_diamond: ``#{channel.name}\n``" for channel in guild.channels if
                     str(channel.id) in server_channels_monitor])

            # the threshold(total messages to achieve to streak) the guild has been set to
            guildThreshold = self.dataBase.getServerThreshold(guild_id)

            guild_voice_threshold = self.dataBase.get_voice_guild_threshold(guild) / 60

            if self.dataBase.track_voice(guild) and self.dataBase.track_word(guild):

                guild_streak_tracker = f":small_blue_diamond: **The server's threshold for voice:**  {int(guild_voice_threshold):0,} minutes\n" \
                                       f":small_blue_diamond: **The server's threshold for words**   {guildThreshold:0,}"

            elif self.dataBase.track_word(guild):
                guild_streak_tracker = f":small_blue_diamond:  **The server's threshold for words**   {guildThreshold:0,}\n" \
                                       f":small_blue_diamond:  **This server has disabled voice monitoring**"

            elif self.dataBase.track_voice(guild):
                guild_streak_tracker = f":small_blue_diamond:**The server's threshold for voice:**  {int(guild_voice_threshold):0,} minutes\n" \
                                       f":small_blue_diamond:  **This server has disabled words monitoring**"

            else:
                guild_streak_tracker = f":small_blue_diamond: **This server has disabled words monitoring:**\n" \
                                       f":small_blue_diamond:  **This server has disabled voice monitoring:**"

            self.embed = dict(
                title=f"**=={str(guild).upper()} STREAK SETTINGS==**",
                color=9127187,
                description=f"{guild_streak_tracker}.\n",
                thumbnail={"url": f"{guild.icon_url}"},
                fields=[dict(name=f"**====================** \n", value=f":book: Total Users in this server\n"
                                                                        f":book: Total Channels in this server\n"
                                                                        "====================", inline=True),
                        dict(name="**====================**", value=f":white_small_square:    {totalUsers:0,}\n"
                                                                    f":white_small_square:    {totalChannels:0,}\n"
                                                                    f"====================", inline=True),
                        dict(name="Text-Channels Monitored",
                             value=f"{channels_monitored}", inline=False), ],

                footer=dict(text=f"HAPPY STREAKING!"),
            )
            await ctx.channel.send(embed=discord.Embed.from_dict(self.embed))

    # this is temporary till all none data is filled
    def fillNoneData(self, guild, user):
        # updating ServerName, will be used to update Database for old info  (temporary will be removed once it has been

        if self.dataBase.getServerName(guild) is None:
            self.dataBase.updateServerName(guild)
            print(f"I have updated {guild.name} to Database")
        try:
            if self.dataBase.getUserName(user) is None:
                self.dataBase.updateUserName(user)
                print(f"I have updated {user} to Database")

        except TypeError:

            print(f"{user} did not exist on database")
            self.dataBase.addUser(guild, user)
            self.dataBase.add_user_global(guild, user)

    @commands.command(
        help="``!streak (Optional:me|global|@someone) ``: A very wide-purpose command, with the arguments basically self-explanatory. If you want to view the global leaderboard, use no arguments.")
    async def streak(self, ctx, *args):

        # getting the guild the message was sent from

        guildID = ctx.guild.id

        guild = ctx.guild

        # check if user has mentioned someone
        mention = ctx.message.mentions

        # get the first word this will be used for $streak me to retrieve current user's streak
        otherMessage = args

        # if user has mentioned someone return the first mention in case they mentioned more than once
        if mention:
            # get the user that was mention
            userMentioned = mention[0]
            # check if the user mentioned is a bot other wise cancel
            if not mention[0].bot:
                # send the information over to another method to send an embed for that user
                # passing over ctx to send message to the channel

                await self.mentionStreak(ctx, userMentioned, guild)

        # check if there's any other messages that were sent
        elif otherMessage:

            # get the first word that was mentioned
            otherMessage = args[0]

            if otherMessage == "me":
                await self.mentionStreak(ctx, ctx.author, guild)

            elif otherMessage == "global":

                await self.globalLeaderBoard(ctx)
        else:

            # return first 25
            leaderBoard = self.dataBase.viewServerLeaderBoard(guildID)

            # get the username of a user and remove anything after their deliminator #

            userNames = []
            for data in leaderBoard:
                serverID = data[0]
                serverName = data[1]
                userName = data[2]
                userID = data[3]
                if userName is None:
                    try:
                        self.dataBase.updateUserName(self.bot.get_user(userID))
                        userNames.append(self.bot.get_user(userID).name)
                    except AttributeError:
                        self.dataBase.removeUser(serverID, userID)
                else:
                    # remove the deliminator as we would only need the name
                    userNames.append(userName.split('#')[0])

                if serverName is None:
                    self.dataBase.updateServerName(self.bot.get_guild(serverID))

            userNames = '\n'.join(userNames)

            usersTotalMessages = '\n'.join([f'{user[4]:0,}' for user in leaderBoard])
            usersStreakDays = '\n'.join([str(user[5]) for user in leaderBoard])

            self.embed = dict(
                title=f"**==STREAK LEADERBOARD==**",
                color=9127187,
                thumbnail={
                    "url": "https://cdn4.iconfinder.com/data/icons/miscellaneous-icons-2-1/200/misc_movie_leaderboards3-512.png"},
                fields=[dict(name="**Users**", value=userNames, inline=True),
                        dict(name="Streak Total", value=usersStreakDays, inline=True),
                        dict(name="Total Words Sent", value=usersTotalMessages, inline=True)],
                footer=dict(text=f"Total Words counted on {self.today} ")
            )
            await ctx.channel.send(embed=discord.Embed.from_dict(self.embed))

    async def globalLeaderBoard(self, ctx):

        # return first 25
        leaderBoard = self.dataBase.viewGlobalLeaderBoard()

        userNames = []

        for data in leaderBoard:
            serverID = data[0]
            serverName = data[1]
            userName = data[2]
            userID = data[3]
            if userName is None:
                self.dataBase.updateUserName(self.bot.get_user(userID))
                userNames.append(self.bot.get_user(userID).name)
            else:
                userNames.append(userName)

            if serverName is None:
                self.dataBase.updateServerName(self.bot.get_guild(serverID))

        userNames = '\n'.join(userNames)

        usersTotalMessages = '\n'.join([f'{user[4]:0,}' for user in leaderBoard])
        usersStreakDays = '\n'.join([str(user[5]) for user in leaderBoard])

        global_threshold = self.dataBase.getGlobalThreshold()

        self.embed = dict(
            title=f"**==GLOBAL STREAK LEADERBOARD==**",
            color=9127187,
            thumbnail={
                "url": "https://cdn4.iconfinder.com/data/icons/miscellaneous-icons-2-1/200/misc_movie_leaderboards3-512.png"},
            fields=[dict(name="**Users**", value=userNames, inline=True),
                    dict(name="Streak Total", value=usersStreakDays, inline=True),
                    dict(name="Words Sent Today", value=usersTotalMessages, inline=True)],
            footer=dict(
                text=f"Total Words counted on {self.today} | Threshold for Global is {global_threshold} (+5 per day) word Count\n"
                     f"Voice time are not counted towards global leaderboard")
        )
        await ctx.channel.send(embed=discord.Embed.from_dict(self.embed))

    # checking for the dates if its a new day
    @tasks.loop(minutes=1)
    async def dateCheck(self):

        currentDay = datetime.today().date().strftime("%d-%m-%Y")


        if self.today != currentDay:
            # keeping tracking of the day  before
            # updating today so it is the correct date
            self.today = currentDay

            self.dataBase.setNewDayStats()

            print("New Day")

    @commands.Cog.listener()
    async def on_member_join(self, user):

        # add the user to the correct server
        if not user.bot:
            print(f"{user} has joined {user.guild.name}")
            self.dataBase.addUser(user.guild, user)

    @commands.Cog.listener()
    async def on_member_remove(self, user):

        # remove the user from data as they have left
        if not user.bot:
            print(f"{user} has left  {user.guild.name}")
            self.dataBase.removeUser(user.guild.id, user.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):

        print(f"New Guild Has Joined {guild.name}")
        # add new guild to the database
        self.dataBase.addNewGuild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):

        print(f"A Guild Has left {guild.name}")
        self.dataBase.removeServer(guild.id)

    @commands.command(help="``!info``: View basic bot information, like user count, server count, latency, etc.")
    async def info(self, ctx):

        # how many server the bot is in
        totalGuilds = len(self.bot.guilds)
        # how many user the bot can see (including bots)
        totalUsers = len(self.bot.users)

        totalChannels = sum([len(guild.channels) for guild in self.bot.guilds])

        latency = int(self.bot.latency * 100)

        guildID = ctx.guild.id

        guild = ctx.author.guild

        # the threshold(total messages to achieve to streak) the guild has been set to
        guildThreshold = self.dataBase.getServerThreshold(guildID)

        guild_voice_threshold = f":white_small_square: Accumulate {int(self.dataBase.get_voice_guild_threshold(guild) / 60)} minutes in  voice call (unmuted) to streak  " \
            if self.dataBase.track_voice(guild) else ''

        self.embed = dict(
            title=f"**==DISCORD STREAK INFO==**",
            color=9127187,
            description=f":white_small_square: Minimum word count for streak is {guildThreshold:0,}.\n"
                        f":white_small_square: Streaks are added when you reach {guildThreshold:0,} words or more.\n"
                        ":white_small_square: Streak will reset at midnight GMT failure to meet word count.\n"
                        f"{guild_voice_threshold}\n",
            thumbnail={"url": "https://cdn3.iconfinder.com/data/icons/shopping-e-commerce-33/980/shopping-24-512.png"},
            fields=[dict(name=f"**====================** \n", value=f":book: Total Servers\n"
                                                                    f":book: Total Players\n"
                                                                    f":book: Total Channels\n"
                                                                    f":book: My Connection\n"
                                                                    "====================", inline=True),

                    dict(name="**====================**", value=f":white_small_square:    {totalGuilds}\n "
                                                                f":white_small_square:    {totalUsers:02,}\n"
                                                                f":white_small_square:    {totalChannels:02,}\n"
                                                                f":white_small_square:    {latency} ms\n"
                                                                f"====================",
                         inline=True),

                    dict(name="**Useful Links**",
                         value=f":white_small_square: [Vote](https://top.gg/bot/685559923450445887) for the bot \n"
                               f":white_small_square: [support channel](https://discord.gg/F6hvm2) for features request| upcoming updates",
                         inline=False),

                    dict(name="**Update**",
                         value=f":white_small_square: **!help** display help command for the bot\n"
                               f":white_small_square: **!streak global** NEW COMMAND SEE GLOBAL LEADERBOARD\n"
                               f":white_small_square: **!streak @someone** to view their summary profile\n"
                               f":white_small_square: **!streak me** to view your own profile \n"
                               f":white_small_square: small Achievement has been added summary profile.\n"
                               f":white_small_square: set threshold for amount words for a streak **!threshold amount** \n",
                         inline=False),

                    ],

            footer=dict(text=f"HAPPY STREAKING!"),
        )
        await ctx.channel.send(embed=discord.Embed.from_dict(self.embed))

    async def mentionStreak(self, ctx, user, guild):

        userName, MsgCount, streakCounter, streaked, highestStreak, lastStreakDay, highMsgCount \
            = self.dataBase.getUserInfo(guild.id, user.id)

        guildThreshold = self.dataBase.getServerThreshold(guild.id)

        # adding emotes based on different stages of streak for current streak only
        # if user has reached 3 or more streak day they get fire streak
        if streakCounter >= 3:

            userStreakFormat = f"{streakCounter} :fire:"

            #  if user reached over 100 streaks they get #100 emote
            if streakCounter >= 100:
                userStreakFormat = f"{streakCounter} :fire: :100: "

        else:
            userStreakFormat = streakCounter

        # message to be put in the footer if they had achieved a streak

        guild_voice_threshold = self.dataBase.get_voice_guild_threshold(guild) / 60
        user_total_voice = self.dataBase.get_user_voice_time(guild, user) / 60

        voice_time_left = int(guild_voice_threshold - user_total_voice)

        # footer message to indicate if the user has received a streak for today
        if streaked:
            footerMessage = "You have claimed your streak for today"

            profile_streak_tracker = f":small_blue_diamond: **You Have Claimed Your Streak For Today**"

        else:
            footerMessage = "You have not claimed the streak for today"

            if self.dataBase.track_voice(guild) and self.dataBase.track_word(guild):

                profile_streak_tracker = f":small_blue_diamond: **Time left to streak with Voice:**  {voice_time_left:0,}m\n" \
                                         f":small_blue_diamond: **Words left to streak:**   {int(guildThreshold - MsgCount):0,}"

            elif self.dataBase.track_word(guild):
                profile_streak_tracker = f":small_blue_diamond: **Words left to streak :**  {int(guildThreshold - MsgCount) :0,}"

            elif self.dataBase.track_voice(guild):
                profile_streak_tracker = f":small_blue_diamond: **Time left to streak with Voice:** {voice_time_left:0,}m"

            else:
                profile_streak_tracker = f":small_blue_diamond: **Words and Voice streaking both disabled**"

        self.embed = dict(
            color=9127187,
            author={"icon_url": f"{user.avatar_url}", "url": f"{user.avatar_url}",
                    "name": f"{userName}'s Profile Summary"},
            fields=[
                dict(name="**Highest Streak**", value=highestStreak, inline=True),
                dict(name="**Current Streak**", value=userStreakFormat, inline=True),
                dict(name=":book: **Other Stats**",
                     value=f":small_blue_diamond: **Last Streaked:**  \u200b {lastStreakDay}\n"
                           f":small_blue_diamond: **Current Word Count:**  \u200b {MsgCount:0,}\n"
                           f":small_blue_diamond: **Total Word Count:**  \u200b {highMsgCount:0,}\n"
                           f"{profile_streak_tracker}",
                     inline=False),

            ],
            # image = {"url": f"{user.avatar_url}"},
            # footer
            footer=dict(text=f"{footerMessage}"),

        )

        # check if the user has achieved any of the milestones
        self.achievementUnlocks(highestStreak, highMsgCount)

        await ctx.channel.send(embed=discord.Embed.from_dict(self.embed))

    def achievementUnlocks(self, userStreak, totalMessage):

        # milestone that will be used for looping
        milestones = {10: "",
                      20: "",
                      40: "",
                      60: "",
                      80: "",
                      100: "",
                      150: ""}

        msgMilestone = {500: "",
                        1000: "",
                        10000: "",
                        50000: "",
                        100000: "",
                        250000: "",
                        500000: ""}

        # loop through the milestone and check if the user has reached the milestone if they have give them diamond
        # else cross

        achievementStreakCheck = '\n'.join(
            [f":gem: {milestone} Streaks" if userStreak >= milestone else f":x: {milestone} Streaks" for milestone in
             milestones])

        achievementMsgCheck = '\n'.join([
            f":gem: {milestone:02,} words" if totalMessage >= milestone else f":x: {milestone:02,} words"
            for milestone in msgMilestone])

        # add the achievement to the embed to display
        achievements = dict(name="**Streak Milestones**",
                            value=f"{achievementStreakCheck}", inline=True)

        achievement2 = dict(name="**Total Words Milestones**",
                            value=f"{achievementMsgCheck}", inline=True)

        bottomBar = dict(name="=====**More Achievements To Come**====", value=f"\u200b")

        self.embed['fields'].append(achievements)
        self.embed['fields'].append(achievement2)
        self.embed['fields'].append(bottomBar)

    # would be used if hosting bot yourself
    def scanCurrentServer(self):

        # scanning al the guild the bot is currently in and return their ID
        for guild in self.bot.guilds:
            self.dataBase.addNewGuild(guild)

    # this is only for debugging not to be used for implementation
    @commands.command(hidden=True)
    async def setstreak(self, ctx, amount):

        testGuildID = 602439523284287508

        if ctx.author.id == 125604422007914497 and ctx.guild.id == testGuildID:
            mentionedUser = ctx.message.mentions[0].name
            mentionedUserID = ctx.message.mentions[0].id
            # give the user a streak point
            self.dataBase.setStreakToUser(testGuildID, mentionedUserID, int(amount))

            await ctx.channel.send(f"{mentionedUser} streak point has been set to {amount} ")

    @commands.command(help="``!help (optional: (category name|command name)``: What do you think I do?")
    async def help(self, ctx, *args):

        if not args:
            # getting list of commands and putting speech bubble over them to make them stand out
            list_of_commands = ','.join(map(lambda word: f'`{word}`', command_event.command_categories))

            embed = dict(
                title=f"**==DISCORD STREAK HELP==**",
                color=9127187,
                thumbnail={
                    "url": "https://cdn3.iconfinder.com/data/icons/shopping-e-commerce-33/980/shopping-24-512.png"},
                fields=[
                    dict(name="**Categories**",
                         value=f"{list_of_commands}",
                         inline=False),

                    dict(name="**Basic Info**",
                         value="To view the commands in each category, do ``!help <category name>``.\n"
                               "To view the help for each command, do ``!help <command name>``.\n",
                         inline=False),

                    dict(name="**Support Channel**",
                         value=f"[Support channel](https://discord.gg/F6hvm2)\n===**You Can**===\n"
                               f":white_small_square: Features request\n"
                               f":white_small_square: Upcoming updates\n"
                               f":white_small_square: Report a bug\n"
                               f":white_small_square: Many more things to  come!\n", inline=False),

                    dict(name="**Other Information**",
                         value=f":white_small_square: [Vote on top.gg](https://top.gg/bot/685559923450445887) \n"
                               f":white_small_square: bots.ondiscord.xyz [pending review]",
                         inline=False),

                ],

                footer=dict(text="We hope you find everything OK!"),

            )

            await ctx.channel.send(embed=discord.Embed.from_dict(embed))
            # no need to go next step
            return

        # if the length of command sent by user is less than 3 (3 is a place holder and can be grown
        if len(args) <= 3:

            command = ' '.join(args).title()

            if command in command_event.command_categories:

                # get list of commands and jon them
                list_of_commands = ' '.join(command_event.command_categories.get(command))

                embed = dict(
                    title=f"**==DISCORD STREAK HELP==**",
                    color=9127187,
                    thumbnail={
                        "url": "https://cdn0.iconfinder.com/data/icons/small-n-flat/24/678110-sign-info-512.png"},
                    fields=[
                        dict(name="**Commands**",
                             value=f"{list_of_commands}",
                             inline=False),
                    ],
                    footer=dict(text="We hope you find everything OK!"),
                )
                await ctx.channel.send(embed=discord.Embed.from_dict(embed))

            elif command.lower() in command_event.commands:

                command_help_info = command_event.commands.get(command.lower())

                embed = dict(
                    title=f"**==DISCORD STREAK HELP==**",
                    color=9127187,
                    thumbnail={
                        "url": "https://cdn0.iconfinder.com/data/icons/small-n-flat/24/678110-sign-info-512.png"},
                    fields=[
                        dict(name="**Commands**", value=f"{command_help_info}",
                             inline=False),
                    ],
                    footer=dict(text="We hope you find everything OK!"),
                )
                await ctx.channel.send(embed=discord.Embed.from_dict(embed))

            else:

                await ctx.channel.send("That command or category doesn't exist!")

    # this is only for debugging not to be used for implementation
    @commands.command(hidden=True)
    async def setmsg(self, ctx, amount):

        testGuildID = 602439523284287508
        if ctx.author.id == 125604422007914497 and ctx.guild.id == testGuildID:
            mentionedUser = ctx.message.mentions[0].name
            mentionedUserID = str(ctx.message.mentions[0].id)
            # give the user a streak point
            self.dataBase.setMsgCountToUser(testGuildID, mentionedUserID, int(amount))

            await ctx.channel.send(f"{mentionedUser} MSG point has been set to {amount} ")

    # this is only for debugging not to be used for implementation
    @commands.command(hidden=True)
    async def debug(self, ctx):

        user_id = 125604422007914497

        if ctx.author.id == user_id:
            active_calls = len(self.dataBase.get_active_calls())
            await ctx.channel.send(f"Active calls: {active_calls}", delete_after=10)


class CommandEvent:

    def __init__(self):
        self.command_categories = {}
        self.commands = {}
        self.set_up_commands()

    def set_up_commands(self):

        # loop through the commands
        for command in bot.get_cog('StreakBot').get_commands():

            # ignore all hidden commands
            if not command.hidden:
                # get the category name
                command_category = command.brief

                # add the commands to the command list dictionary
                self.commands[command.name] = command.help

                # check if a key already exist for this category
                if self.command_categories.get(command.brief) is None:

                    self.command_categories[command_category] = [f"`{command.name}`"]

                else:
                    # otherwise append to an existing key
                    self.command_categories[command_category].append(f"`{command.name}`")


if __name__ == "__main__":
    bot.add_cog(StreakBot(bot))
    command_event = CommandEvent()
    bot.run("")

"""
Methods to update when changing Json

when guild joins
when user join guilds

"""
