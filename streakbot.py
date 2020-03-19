import discord
import json
from discord.ext import commands
from discord.ext import tasks
from datetime import datetime
import time

bot = commands.Bot(command_prefix='$')

usersInCurrentGuild = {}

streakData = json.load(open("streak.json", "r+"))


class StreakBot(commands.Cog):
    today = datetime.today().date().strftime("%d-%m-%Y")
    yesterday = None

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'We have logged in as {self.bot.user}\n')
        self.dateCheck.start()

        # # scanning al the guild the bot is currently in and return their ID
        # for guild in self.bot.guilds:
        #
        #     # create a list to hold each users for different guild
        #     usersInCurrentGuild[guild.id] = {}
        #
        #     for member in guild.members:
        #
        #         # checking if the user is a bot as we wont be tracking the bots
        #         if not member.bot:
        #             # add those users into the system
        #             # each member has total message, days of streak
        #             usersInCurrentGuild[guild.id].update({member.id: [0, 0, False]})
        #         else:
        #             continue
        #
        # json.dump(usersInCurrentGuild, open("streak.json", "w"))

    @commands.Cog.listener()
    async def on_message(self, message):
        user = message.author
        userId = str(message.author.id)
        messageLength = len(message.content.split())
        guildMessageFrom = str(message.guild.id)

        if not user.bot:

            # load the current users  total messages
            currentUserTotalMessage = streakData[guildMessageFrom][userId][0]

            # check if they had streaked already
            streakedToday = streakData[guildMessageFrom][userId][2]

            # adding total total messages to the user
            streakData[guildMessageFrom][userId][0] += messageLength

            # if user has not been given a streak for today but has sent over 100 messages
            if not streakedToday and currentUserTotalMessage >= 100:
                # give the user a streak point
                streakData[guildMessageFrom][userId][1] += 1

                # change the boolean to True as they have received a streak for today
                streakData[guildMessageFrom][userId][2] = True

    # streak commands
    @commands.command()
    async def streak(self, ctx):

        # getting the guild the message was sent from
        guildMessageFrom = str(ctx.guild.id)

        # retrieving the data for that guild
        streakUsersFromGuild = streakData[guildMessageFrom]

        # obtain the users from that specific guild
        usersID = list(streakUsersFromGuild.keys())


        # unpack the total messages, and streak days
        totalMessages, streakDays, _ = list(zip(*streakUsersFromGuild.values()))

        # sorting the users based on the highest streak (will be changing to streak days)
        streakDays, usersID, totalMessages, = zip(*sorted(zip(streakDays, usersID, totalMessages, ), reverse=True))

        # converting the id to their Original Names
        userNames = "__\n__".join([self.bot.get_user(int(user)).name for user in usersID[0:25]])

        # creating a String containing all the total messages
        usersTotalMessages = "\n".join([str(total) for total in totalMessages[0:25]])

        # creating a String containing all the streaks
        usersStreakDays = "\n".join([str(streak) for streak in streakDays[0:25]])

        embed = dict(
            title=f"**==STREAK LEADERBOARD==**",
            color=9127187,
            thumbnail={
                "url": "https://cdn4.iconfinder.com/data/icons/miscellaneous-icons-2-1/200/misc_movie_leaderboards3-512.png"},
            fields=[dict(name="**Users**", value=userNames, inline=True),
                    dict(name="Streak Total", value=usersStreakDays, inline=True),
                    dict(name="Total Words Sent", value=usersTotalMessages, inline=True)],
            footer=dict(text=f"Total Words counted on {self.today}")
        )
        await ctx.channel.send(embed=discord.Embed.from_dict(embed))

    # checking for the dates if its a new day
    @tasks.loop(minutes=5)
    async def dateCheck(self):

        currentDay = datetime.today().date().strftime("%d-%m-%Y")

        if self.today != currentDay:
            # keeping tracking of the day  before
            yesterday = self.today
            # updating today so it is the correct date
            self.today = currentDay

            print("New Day")
            time.sleep(5)
            self.checkStreaks()

    @staticmethod
    def checkStreaks():

        # we will be looping through the servers to add or reset the streak
        for guild in streakData:

            # check each members in the guild
            for member in streakData[guild]:

                # retrieve total messages sent
                memberTotalMessage = streakData[guild][member][0]

                # if the user has sent more than 20 words today
                if memberTotalMessage >= 100:

                    # reset their messages sent
                    streakData[guild][member][0] = 0

                    #  change streaked today to false as its a new day so no streak yet
                    streakData[guild][member][2] = False

                else:
                    # reset their messages sent
                    streakData[guild][member][0] = 0

                    # clear the streak if they had any
                    streakData[guild][member][1] = 0

        # back up the file
        json.dump(streakData, open("streak.json", "w"))

    @commands.Cog.listener()
    async def on_member_join(self, member):

        guildMemberJoined = str(member.guild.id)

        print(f"New user has joined {member.guild.name}")

        # add the user to the correct server
        if not member.bot:
            streakData[guildMemberJoined].update({str(member.id): [0, 0, False]})

        json.dump(streakData, open("streak.json", "w"))

    @commands.Cog.listener()
    async def on_member_remove(self, member):

        guildMemberJoined = str(member.guild.id)

        print(f"user has left  {member.guild.name}")

        # remove the user from data as they have left
        if not member.bot:
            streakData[guildMemberJoined].pop(str(member.id))

        json.dump(streakData, open("streak.json", "w"))

    @commands.Cog.listener()
    async def on_guild_join(self, guild):

        print("New Guild Has Joined")

        guildId = str(guild.id)

        streakData.update({guildId: {}})

        for member in guild.members:
            # checking if the user is a bot as we wont be tracking the bots
            if not member.bot:
                # add those users into the system
                # each member has total message, days of streak
                streakData[guildId].update({str(member.id): [0, 0, False]})
            else:
                continue

        json.dump(streakData, open("streak.json", "w"))

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):

        print(f"A Guild Has left {guild.name}")

        guildId = str(guild.id)

        # remove the server from data
        streakData.pop(guildId)

        # update the data
        json.dump(streakData, open("streak.json", "w"))

    @commands.command()
    async def info(self, ctx):

        # how many server the bot is in
        totalGuilds = len(self.bot.guilds)

        totalChannels = sum([len(guild.channels) for guild in self.bot.guilds])

        latency = int(self.bot.latency * 100)

        embed = dict(
            title=f"**==DISCORD STREAK INFO==**",
            color=9127187,
            description=
            ":white_small_square: Minimum word count for streak is 100.\n"
            ":white_small_square: Streaks are added when you reach 100 words or more.\n"
            ":white_small_square: Streak will reset at midnight GMT failure to meet word count.\n"
            ,
            thumbnail={
                "url": "https://cdn3.iconfinder.com/data/icons/shopping-e-commerce-33/980/shopping-24-512.png"},
            fields=[dict(name=f"**====================** \n"
                         , value=f":book: Total Servers\n"
                                 f":book: Total Channels\n"
                                 f":book: My Connection\n"
                                 "====================", inline=True),

                    dict(name="**====================**", value=f":white_small_square:    {totalGuilds}\n "
                                                                f":white_small_square:    {totalChannels}\n"
                                                                f":white_small_square:    {latency} ms\n"
                                                                f"====================",
                         inline=True),

                    ],

            footer=dict(text=f"HAPPY STREAKING!"),
        )
        await ctx.channel.send(embed=discord.Embed.from_dict(embed))


    # this is only needed if you had the old system and need to add a third boolean

    def addBoolean(self):

        # we will be looping through the servers to add or reset the streak
        for guild in streakData:

            # check each members in the guild
            for member in streakData[guild]:
                streakData[guild][member].append(False)

        # back up the file
        json.dump(streakData, open("streak.json", "w"))

    @commands.command()
    async def streakme(self, ctx):

        # getting the guild the message was sent from
        guildMessageFrom = str(ctx.guild.id)

        # the user's Name
        userName = ctx.author

        # retrieving the data for that guild
        streakUsersFromGuild = streakData[guildMessageFrom]

        # unpack the user's data
        userTotalStreak,userTotalMessages,_ = streakUsersFromGuild[str(ctx.author.id)]

        # adding emotes based on different stages of streak
        # if user has reached 3 or more streak day they get fire streak
        if userTotalStreak >= 3:

            userStreakFormat = f"{userTotalStreak} :fire:"

            #  if user reached over 100 streaks they get #100 emote
            if userTotalStreak >= 100:
                userStreakFormat = f"{userTotalStreak} :fire: :100: "

        else:
            userStreakFormat = userTotalStreak

        streakClaimedMessage = "You have claimed your streak for today"

        footerMessage = streakClaimedMessage if userTotalMessages >=  100 else f"Words count left till streak {100 - userTotalMessages}"

        userTotalMessages = userTotalMessages if userTotalMessages < 100 else f"{userTotalMessages} "



        embed = dict(
            title=f"**=={userName} Profile Streak==**",
            color=9127187,
            thumbnail = {"url": f"{ctx.author.avatar_url}"},
            fields=[
                dict(name="Word Count", value=userTotalMessages, inline=True),
                    dict(name="Streak Total", value=userStreakFormat, inline=True),
                dict(name="Last Streak", value=f"{self.today}", inline=True),

                    ],

            # footer
            footer=dict(text=f"You have claimed your streak for today"),


        )
        await ctx.channel.send(embed=discord.Embed.from_dict(embed))

    # will be used for debugging when need to make changes
    @commands.command()
    async def updateData(self, ctx):
        if ctx.author.id == 125604422007914497:
            json.dump(streakData, open("streak.json", "w"))
            await ctx.channel.send("Database has been backed up")




if __name__ == "__main__":
    bot.add_cog(StreakBot(bot))
    bot.remove_command("help")

    bot.run("")