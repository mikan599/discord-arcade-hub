import os
import re
from pathlib import Path
from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.app_commands import Range, Choice

from features.minesweeper import (
    generate_board_text,
    generate_board_text_custom,
    DIFFICULTY,
)

from features.gomoku import GomokuGame, X, O
from features.gomoku_render import render_gomoku_png

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN が取得できていません。.env または環境変数を確認してください。")

gomoku_games: dict[int, GomokuGame] = {}

MOVE_RE = re.compile(r"^\s*(\d{1,2})\s+(\d{1,2})\s*$")


class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # グローバル同期（どのサーバでもコマンドが出る）
        await self.tree.sync()


client = MyClient()


@client.event
async def on_ready():
    print(f"Logged in as: {client.user} (id={client.user.id})")


@client.tree.command(name="ping", description="動作確認")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong")


@client.tree.command(name="minesweeper", description="伏せ字マインスイーパーを生成します")
@app_commands.describe(
    difficulty="easy/normal/hard/insane（指定すると size/bombs より優先）",
    size="盤面サイズ（1辺）",
    bombs="爆弾の数",
    safe_radius="中央の安全エリア半径（1なら3x3が安全）",
)
async def minesweeper_cmd(
    interaction: discord.Interaction,
    difficulty: str | None = None,
    size: Range[int, 2, 14] = 10,
    bombs: Range[int, 0, 200] = 15,
    safe_radius: Range[int, 0, 3] = 1,
):
    if difficulty:
        d = difficulty.lower().strip()
        if d not in DIFFICULTY:
            d = "normal"
        board = generate_board_text(d)
        await interaction.response.send_message(board)
        return

    board = generate_board_text_custom(size, bombs, safe_radius=safe_radius)
    await interaction.response.send_message(board)


def _is_thread_channel(ch) -> bool:
    return isinstance(ch, discord.Thread)


def _fmt_user(u: discord.User | discord.Member) -> str:
    return getattr(u, "display_name", u.name)


async def _send_board_image(thread: discord.Thread, game: GomokuGame, *, note: str | None = None):
    png = render_gomoku_png(game)
    if note:
        await thread.send(note)
    await thread.send(file=discord.File(fp=png, filename="gomoku.png"))


@client.tree.command(name="gomoku_start", description="五目並べを開始（publicスレッド 1440分で続行）")
@app_commands.describe(
    mode="pvp か ai",
    side="自分が先手(黒)か後手(白)か",
    opponent="pvp の相手",
    size="盤面サイズ",
    difficulty="ai の強さ",
)
@app_commands.choices(
    mode=[
        Choice(name="pvp", value="pvp"),
        Choice(name="ai", value="ai"),
    ],
    side=[
        Choice(name="first", value="X"),
        Choice(name="second", value="O"),
    ],
    size=[
        Choice(name="9", value=9),
        Choice(name="11", value=11),
        Choice(name="13", value=13),
        Choice(name="15", value=15),
    ],
    difficulty=[
        Choice(name="easy", value="easy"),
        Choice(name="normal", value="normal"),
        Choice(name="hard", value="hard"),
    ],
)
async def gomoku_start(
    interaction: discord.Interaction,
    mode: Choice[str],
    side: Choice[str],
    size: Choice[int] | None = None,
    opponent: discord.Member | None = None,
    difficulty: Choice[str] | None = None,
):
    if not interaction.guild or not interaction.channel:
        await interaction.response.send_message("サーバー内のチャンネルで実行してください。")
        return

    starter = interaction.user
    want_side = side.value  # "X" or "O"
    board_size = size.value if size else 15

    # pvp相手チェック
    if mode.value == "pvp":
        if opponent is None:
            await interaction.response.send_message("pvp では opponent を指定してください。")
            return
        if opponent.bot:
            await interaction.response.send_message("botは対戦相手にできません（ai モードを使ってください）。")
            return
        if opponent.id == starter.id:
            await interaction.response.send_message("自分自身とは対戦できません。")
            return
    else:
        opponent = None

    # スレッド生成
    if _is_thread_channel(interaction.channel):
        thread: discord.Thread = interaction.channel  # type: ignore
        await interaction.response.send_message("このスレッドで五目並べを開始します。")
    else:
        parent = interaction.channel
        try:
            name = "五目並べ: " + _fmt_user(starter)
            if mode.value == "pvp" and opponent:
                name += " vs " + _fmt_user(opponent)
            else:
                name += " vs AI"
            thread = await parent.create_thread(
                name=name,
                type=discord.ChannelType.public_thread,
                auto_archive_duration=1440,
                reason="gomoku game thread",
            )
        except Exception as e:
            await interaction.response.send_message(f"スレッド作成に失敗しました。権限を確認してください。\n{e}")
            return

        await interaction.response.send_message(
            f"五目並べスレッドを作成しました。続きはここで進行します: {thread.jump_url}"
        )

    if thread.id in gomoku_games:
        await thread.send("このスレッドでは既に対局が進行中です。終了してから開始してください。")
        return

    # ゲーム生成（先手/後手の割当）
    if mode.value == "pvp" and opponent:
        if want_side == "X":
            game = GomokuGame(size=board_size, mode="pvp", player_x=starter.id, player_o=opponent.id)
            await thread.send(f"開始: 先手={starter.mention}, 後手={opponent.mention}（先手のみ禁じ手あり）")
        else:
            game = GomokuGame(size=board_size, mode="pvp", player_x=opponent.id, player_o=starter.id)
            await thread.send(f"開始: 先手={opponent.mention}, 後手={starter.mention}（先手のみ禁じ手あり）")
    else:
        lvl = difficulty.value if difficulty else "hard"
        if want_side == "X":
            # 人間が先手、AIが後手
            game = GomokuGame(size=board_size, mode="ai", player_x=starter.id, player_o=None, ai_level=lvl)
            await thread.send(f"開始: 先手={starter.mention}, 後手=AI (level={lvl})（先手のみ禁じ手あり）")
        else:
            # 人間が後手、AIが先手（AIにも禁じ手が適用される）
            game = GomokuGame(size=board_size, mode="ai", player_x=None, player_o=starter.id, ai_level=lvl)
            await thread.send(f"開始: 先手=AI (level={lvl}), 後手={starter.mention}（先手のみ禁じ手あり）")

    gomoku_games[thread.id] = game
    await _send_board_image(thread, game)
    await thread.send("操作: スレッド内で `x y` を送信（例: `8 8`）")

    # AIが先手なら、開始直後に1手打つ
    if game.mode == "ai" and game.is_ai_turn():
        ax, ay = game.ai_move()
        game._place_raw(ax, ay, game.turn)  # turn側がAI
        await _send_board_image(thread, game, note=f"AI move: {ax+1} {ay+1}")


@client.tree.command(name="gomoku_show", description="盤面を再表示（スレッド内）")
async def gomoku_show(interaction: discord.Interaction):
    if not interaction.guild or not interaction.channel:
        await interaction.response.send_message("サーバー内のスレッドで実行してください。")
        return
    if not _is_thread_channel(interaction.channel):
        await interaction.response.send_message("対局はスレッド内で進行します。")
        return
    thread: discord.Thread = interaction.channel  # type: ignore
    game = gomoku_games.get(thread.id)
    if not game:
        await interaction.response.send_message("このスレッドには進行中の対局がありません。")
        return

    png = render_gomoku_png(game)
    await interaction.response.send_message(file=discord.File(fp=png, filename="gomoku.png"))


@client.tree.command(name="gomoku_resign", description="投了（スレッド内）")
async def gomoku_resign(interaction: discord.Interaction):
    if not interaction.guild or not interaction.channel:
        await interaction.response.send_message("サーバー内のスレッドで実行してください。")
        return
    if not _is_thread_channel(interaction.channel):
        await interaction.response.send_message("対局はスレッド内で進行します。")
        return
    thread: discord.Thread = interaction.channel  # type: ignore
    game = gomoku_games.get(thread.id)
    if not game:
        await interaction.response.send_message("このスレッドには進行中の対局がありません。")
        return

    uid = interaction.user.id
    is_player = (game.player_x == uid) or (game.player_o == uid)
    is_admin = isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_threads

    if not (is_player or is_admin):
        await interaction.response.send_message("当事者または管理権限のある人だけ投了できます。")
        return

    game.finished = True
    # 投了した側の逆が勝ち
    if uid == game.player_x:
        game.winner = O
    else:
        game.winner = X

    await interaction.response.send_message("投了しました。")
    await _send_board_image(thread, game)
    gomoku_games.pop(thread.id, None)


@client.tree.command(name="gomoku_end", description="対局を終了（スレッド内）")
async def gomoku_end(interaction: discord.Interaction):
    if not interaction.guild or not interaction.channel:
        await interaction.response.send_message("サーバー内のスレッドで実行してください。")
        return
    if not _is_thread_channel(interaction.channel):
        await interaction.response.send_message("対局はスレッド内で進行します。")
        return

    thread: discord.Thread = interaction.channel  # type: ignore
    game = gomoku_games.get(thread.id)
    if not game:
        await interaction.response.send_message("このスレッドには進行中の対局がありません。")
        return

    uid = interaction.user.id
    is_player = (game.player_x == uid) or (game.player_o == uid)
    is_admin = isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_threads

    if not (is_player or is_admin):
        await interaction.response.send_message("当事者またはスレッド管理権限のある人だけ終了できます。")
        return

    gomoku_games.pop(thread.id, None)
    await interaction.response.send_message("対局を終了しました。")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.Thread):
        return

    thread = message.channel
    game = gomoku_games.get(thread.id)
    if not game:
        return

    # 対局者で、かつ手番の人だけ受け付ける（AI番は無視）
    if not game.can_play(message.author.id):
        return

    m = MOVE_RE.match(message.content)
    if not m:
        return

    x = int(m.group(1))
    y = int(m.group(2))

    ok, msg = game.place(x, y, message.author.id)
    if not ok:
        await thread.send(f"{message.author.mention} {msg}")
        return

    await _send_board_image(thread, game)

    if game.finished:
        gomoku_games.pop(thread.id, None)
        return

    # AI応手（AIの番なら打つ）
    if game.mode == "ai" and game.is_ai_turn():
        ax, ay = game.ai_move()
        game._place_raw(ax, ay, game.turn)
        await _send_board_image(thread, game, note=f"AI move: {ax+1} {ay+1}")
        if game.finished:
            gomoku_games.pop(thread.id, None)


client.run(TOKEN)
