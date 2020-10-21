import io
import copy
import asyncio
import textwrap
import traceback
from contextlib import redirect_stdout
from subprocess import PIPE

import discord
import aiosqlite
from discord.ext import commands

from utils.globals import command_embed


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None

    @commands.command(hidden=True)
    @commands.is_owner()
    async def clr(self, ctx, amount: int = 1):
        """[Owner Only] Remove the given amount of messages."""
        amount += 1
        await ctx.channel.purge(limit=amount)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def load(self, ctx, *, cog: str):
        """[Owner Only] Loads a module.

        Use cogs.cog_name as cog parameter.
        """

        try:
            self.bot.load_extension(cog)
        except Exception as exc:
            await ctx.send(f"""```prolog\n{type(exc).__name__}\n{exc}```""")
        else:
            await ctx.message.add_reaction("✅")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, *, cog: str):
        """[Owner Only] Unloads a module.

        Use cogs.cog_name as cog parameter.
        """

        try:
            self.bot.unload_extension(cog)
        except Exception as exc:
            await ctx.send(f"""```prolog\n{type(exc).__name__}\n{exc}```""")
        else:
            await ctx.message.add_reaction("✅")

    @commands.command(name="reload", aliases=["rld"], hidden=True)
    @commands.is_owner()
    async def _reload(self, ctx, *, cog: str):
        """[Owner Only] Reloads a module.

        Use cogs.cog_name as cog parameter.
        """

        try:
            self.bot.reload_extension(cog)
        except Exception as exc:
            await ctx.send(f"""```prolog\n{type(exc).__name__}\n{exc}```""")
        else:
            await ctx.message.add_reaction("✅")

    @commands.command(aliases=["kys", "die"], hidden=True)
    @commands.is_owner()
    async def shutdown(self, ctx):
        """[Owner Only] Kills the bot session."""
        await ctx.send("Successfully gone offline.")
        await self.bot.logout()

    @commands.command(hidden=True)
    @commands.is_owner()
    async def runas(self, ctx, member: discord.Member, *, command: str):
        """[Owner Only] Run a command as if you were the user."""
        msg = copy.copy(ctx.message)
        msg._update(dict(channel=ctx.channel, content=ctx.prefix + command))
        msg.author = member
        new_ctx = await ctx.bot.get_context(msg)
        try:
            await ctx.bot.invoke(new_ctx)
        except Exception as exc:
            await ctx.send(f"""```prolog\n{type(exc).__name__}\n{exc}```""")

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])
        return content.strip("` \n")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def exc(self, ctx, *, body: str):
        """[Owner Only] Evaluates a code."""
        try:
            env = {
                "bot": self.bot,
                "ctx": ctx,
                "channel": ctx.channel,
                "author": ctx.author,
                "guild": ctx.guild,
                "message": ctx.message,
                "_": self._last_result,
            }

            env.update(globals())

            body = self.cleanup_code(body)
            stdout = io.StringIO()

            to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

            try:
                exec(to_compile, env)
            except Exception as e:
                return await ctx.send(f"```py\n{e.__class__.__name__}: {e}\n```")

            func = env["func"]
            try:
                with redirect_stdout(stdout):
                    ret = await func()
            except Exception:
                value = stdout.getvalue()
                await ctx.send(f"```py\n{value}{traceback.format_exc()}\n```")
            else:
                value = stdout.getvalue()
                try:
                    await ctx.message.add_reaction("✅")
                except discord.Forbidden:
                    pass

                if not ret:
                    if value:
                        await ctx.send(f"```py\n{value}\n```")
                else:
                    self._last_result = ret
                    await ctx.send(f"```py\n{value}{ret}\n```")
        except Exception as exc:
            await ctx.send(exc)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def speedtest(self, ctx):
        """[Owner Only] Run a speedtest directly from Discord."""
        msg = await ctx.send("Running the speedtest...")
        process = await asyncio.create_subprocess_shell(
            "speedtest-cli --simple", stdin=None, stderr=PIPE, stdout=PIPE
        )
        ret = (await process.stdout.read()).decode("utf-8").strip()
        await msg.edit(content=f"""```prolog\n{ret}```""")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def sql(self, ctx, *, query: str):
        """[Owner Only] Run a query."""
        async with self.bot.pool.acquire() as conn:
            try:
                res = await conn.fetch(query)
            except Exception as exc:
                return await ctx.send(f"```prolog\n{exc}```")
            if res:
                await ctx.send(
                    f"""```asciidoc\nSuccessful query\n----------------\n\n{res}```"""
                )
            else:
                await ctx.send("There are no results.")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def admin(self, ctx):
        """[Owner Only] Display an admin panel."""
        try:
            profiles = await self.bot.pool.fetch("SELECT * FROM profile;")
            prefixes = await self.bot.pool.fetch(
                "SELECT * FROM server WHERE prefix <> '-';"
            )
            guilds = await self.bot.pool.fetch("SELECT * FROM server;")
            total_commands = await self.bot.pool.fetchval(
                "SELECT SUM(used) FROM command"
            )

            embed = discord.Embed(title="Admin Panel", color=self.bot.color)
            embed.add_field(name="Profiles", value=len(profiles))
            embed.add_field(name="Prefixes", value=len(prefixes))
            embed.add_field(name="Guilds", value=len(guilds))
            embed.add_field(
                name="Commands Used (Session)", value=self.bot.commands_used
            )
            embed.add_field(name="Commands Used (Lifetime)", value=total_commands)
            await ctx.send(embed=embed)
        except Exception as exc:
            await ctx.send(f"""```prolog\n{type(exc).__name__}\n{exc}```""")

    @commands.group(invoke_without_command=True, hidden=True)
    @commands.is_owner()
    async def cmd(self, ctx, commands: str = None):
        """[Owner Only] Get usage information for 'cmd' command."""
        embed = command_embed(ctx, self.bot.get_command(ctx.command.name))
        await ctx.send(embed=embed)

    @cmd.command(hidden=True)
    async def ls(self, ctx):
        """[Owner Only] Lists commands table."""
        async with ctx.typing():
            rows = [
                tuple(i) for i in await self.bot.pool.fetch("SELECT * FROM command;")
            ]
            await self.bot.paginator.Paginator(title="Commands", entries=rows).paginate(
                ctx
            )

    @cmd.command(hidden=True)
    async def addall(self, ctx):
        """[Owner Only] Insert commands into commands table."""
        async with ctx.typing():
            for command in self.bot.walk_commands():
                fmt = str(command).strip()
                if not await self.bot.pool.fetchrow(
                    'SELECT * FROM command WHERE "name"=$1;', fmt
                ):
                    await self.bot.pool.execute(
                        'INSERT INTO command ("name") VALUES ($1);', fmt
                    )

    @cmd.command(hidden=True)
    async def update(self, ctx, command_id, *, name):
        try:
            await self.bot.pool.execute(
                'UPDATE command SET "name"=$1 WHERE id=$2;', name, command_id
            )
            await ctx.send("Command successfully updated.")
        except Exception as exc:
            await ctx.send(f"""```prolog\n{type(exc).__name__}\n{exc}```""")

    @cmd.command(hidden=True)
    async def delete(self, ctx, command_id):
        try:
            await self.bot.pool.execute("DELETE FROM command WHERE id=$1;", command_id)
            await ctx.send("Command successfully deleted.")
        except Exception as exc:
            await ctx.send(f"""```prolog\n{type(exc).__name__}\n{exc}```""")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def insert_guild(self, ctx):
        async with ctx.typing():
            for guild in self.bot.guilds:
                if not await self.bot.pool.fetchrow(
                    "SELECT * FROM server WHERE id=$1;", guild.id
                ):
                    await self.bot.pool.execute(
                        'INSERT INTO server (id, "prefix") VALUES ($1, $2);',
                        guild.id,
                        self.bot.config.default_prefix,
                    )
            await ctx.send("""```css\nGuilds successfully inserted.```""")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def insert_profiles(self, ctx):
        async with ctx.typing():
            async with aiosqlite.connect("main.sqlite") as conn:
                async with conn.execute("SELECT * FROM profiles") as pool:
                    rows = await pool.fetchall()
                    for row in rows:
                        await self.bot.pool.execute(
                            'INSERT INTO profile (id, "platform", "name") VALUES ($1, $2, $3)',
                            row[0],
                            row[1],
                            row[2],
                        )
            await ctx.send("""```css\nProfiles successfully inserted.```""")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def insert_prefixes(self, ctx):
        async with ctx.typing():
            async with aiosqlite.connect("main.sqlite") as conn:
                async with conn.execute("SELECT * FROM prefixes") as pool:
                    rows = await pool.fetchall()
                    for row in rows:
                        try:
                            await self.bot.pool.execute(
                                "UPDATE server SET prefix=$1 WHERE id=$2",
                                row[1],
                                int(row[0]),
                            )
                        except Exception as exc:
                            print(exc)
            await ctx.send("""```css\nPrefixes successfully updated.```""")

    @commands.command(aliases=["medals", "quick", "quickplay", "comp", "competitive"])
    async def awards(self, ctx):
        message = (
            "This command has been deprecated."
            f" To see your whole quickplay/competitive statistics run `{ctx.prefix}stats <pc/psn/xbl> <battletag/username>`."
            " For more information run the `help` command."
        )
        await ctx.send(message)


def setup(bot):
    bot.add_cog(Owner(bot))
