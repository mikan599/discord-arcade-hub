import random
from dataclasses import dataclass
from collections import deque

@dataclass(frozen=True)
class MSConfig:
    size: int
    bomb_rate: float
    safe_radius: int

DIFFICULTY = {
    "easy":   MSConfig(size=8,  bomb_rate=0.10, safe_radius=1),
    "normal": MSConfig(size=10, bomb_rate=0.15, safe_radius=1),
    "hard":   MSConfig(size=10, bomb_rate=0.20, safe_radius=1),
    "insane": MSConfig(size=10, bomb_rate=0.25, safe_radius=1),
}

NUM_EMOJI = {
    0: ":zero:",
    1: ":one:",
    2: ":two:",
    3: ":three:",
    4: ":four:",
    5: ":five:",
    6: ":six:",
    7: ":seven:",
    8: ":eight:",
}
DEFAULT_BOMB_EMOJI = ":bomb:"

# 状態表現
UNKNOWN = None          # 未開示
FLAG = -9               # 爆弾確定（旗）
# 開示済みは 0..8 を入れる

def _in_bounds(n: int, x: int, y: int) -> bool:
    return 0 <= x < n and 0 <= y < n

def _neighbors(x: int, y: int):
    return [
        (x-1, y-1), (x, y-1), (x+1, y-1),
        (x-1, y),           (x+1, y),
        (x-1, y+1), (x, y+1), (x+1, y+1),
    ]

def _reveal_with_zero_flood(grid, state, x, y):
    """(x,y) を開ける。0なら連鎖的に周囲も開ける（本来のマインスイーパー挙動）"""
    n = len(grid)
    q = deque()
    q.append((x, y))

    while q:
        cx, cy = q.popleft()
        if not _in_bounds(n, cx, cy):
            continue
        if state[cx][cy] is not UNKNOWN:
            continue
        if grid[cx][cy] == -1:
            # ソルバー検査中に爆弾を開けることは「論理破綻」なので弾く
            raise RuntimeError("Solver tried to reveal a bomb (invalid state).")
        state[cx][cy] = grid[cx][cy]
        if grid[cx][cy] == 0:
            for nx, ny in _neighbors(cx, cy):
                if _in_bounds(n, nx, ny) and state[nx][ny] is UNKNOWN:
                    q.append((nx, ny))

def _apply_basic_deductions(grid, state):
    """
    基本2規則で推論を進める。
    進展があれば True, なければ False を返す。
    """
    n = len(grid)
    progressed = False

    for x in range(n):
        for y in range(n):
            v = state[x][y]
            if v is UNKNOWN or v == FLAG:
                continue
            if not (0 <= v <= 8):
                continue

            unknowns = []
            flagged = 0
            for nx, ny in _neighbors(x, y):
                if not _in_bounds(n, nx, ny):
                    continue
                sv = state[nx][ny]
                if sv is UNKNOWN:
                    unknowns.append((nx, ny))
                elif sv == FLAG:
                    flagged += 1

            if not unknowns:
                continue

            # 規則1: 旗が数字と同数なら残りは全部安全
            if flagged == v:
                for ux, uy in unknowns:
                    _reveal_with_zero_flood(grid, state, ux, uy)
                    progressed = True

            # 規則2: 未確定 + 旗 = 数字 なら未確定は全部爆弾
            elif flagged + len(unknowns) == v:
                for ux, uy in unknowns:
                    if state[ux][uy] is UNKNOWN:
                        state[ux][uy] = FLAG
                        progressed = True

    return progressed

def is_solvable_no_guess(grid, safe, *, use_zero_flood=True, max_steps=10000) -> bool:
    """
    「推測なしで解けるか」を検査。
    ここでの推測なし = 基本2規則（+0連鎖開示）だけで最後まで開けられること。
    """
    n = len(grid)
    state = [[UNKNOWN for _ in range(n)] for _ in range(n)]

    try:
        for (x, y) in safe:
            if grid[x][y] == -1:
                return False
            if use_zero_flood:
                _reveal_with_zero_flood(grid, state, x, y)
            else:
                state[x][y] = grid[x][y]
    except RuntimeError:
        return False

    steps = 0
    while steps < max_steps:
        steps += 1
        progressed = _apply_basic_deductions(grid, state)
        if not progressed:
            break

    for x in range(n):
        for y in range(n):
            if grid[x][y] != -1 and state[x][y] in (UNKNOWN, FLAG):
                return False
    return True

def _make_safe_set(n: int, safe_radius: int):
    cx = cy = n // 2
    safe = set()
    r = max(0, int(safe_radius))
    for x in range(cx - r, cx + r + 1):
        for y in range(cy - r, cy + r + 1):
            if _in_bounds(n, x, y):
                safe.add((x, y))
    return safe

def _to_discord_text(grid, safe, header: str, *, bomb_emoji: str) -> str:
    n = len(grid)
    SEP = "\u200b"  # spoiler同士がくっついて |||| にならないようにする
    lines = []
    for y in range(n):
        row = []
        for x in range(n):
            cell = bomb_emoji if grid[x][y] == -1 else NUM_EMOJI[grid[x][y]]
            row.append(cell if (x, y) in safe else f"||{cell}||")
        lines.append(SEP.join(row))
    return header + "\n".join(lines)

def generate_board_text(
    difficulty: str = "normal",
    *,
    max_tries: int = 300,
    bomb_emoji: str = DEFAULT_BOMB_EMOJI,
) -> str:
    """難易度指定（割合で爆弾） + 推測不要（基本2規則）で解ける盤面のみ返す"""
    if difficulty not in DIFFICULTY:
        difficulty = "normal"
    cfg = DIFFICULTY[difficulty]
    n = cfg.size
    safe = _make_safe_set(n, cfg.safe_radius)

    for _ in range(max_tries):
        grid = [[0 for _ in range(n)] for _ in range(n)]

        # 爆弾配置（割合）
        for x in range(n):
            for y in range(n):
                if (x, y) in safe:
                    continue
                if random.random() < cfg.bomb_rate:
                    grid[x][y] = -1

        # 数字計算
        for x in range(n):
            for y in range(n):
                if grid[x][y] == -1:
                    continue
                cnt = 0
                for nx, ny in _neighbors(x, y):
                    if _in_bounds(n, nx, ny) and grid[nx][ny] == -1:
                        cnt += 1
                grid[x][y] = cnt

        # safe内に0が無いと面白さが減るので、あればOK
        if safe and all(grid[x][y] != 0 for (x, y) in safe):
            continue

        # 推測不要で解ける盤面のみ採用
        if not is_solvable_no_guess(grid, safe):
            continue

        actual_bombs = sum(
            1 for x in range(n) for y in range(n)
            if grid[x][y] == -1
        )

        header = f"[{difficulty}] size={n} bombs={actual_bombs}\n"
        text = _to_discord_text(grid, safe, header, bomb_emoji=bomb_emoji)

        if len(text) <= 1500:
            return text

    return f"[{difficulty}] failed to generate (try again)"

def generate_board_text_custom(
    size: int,
    bombs: int,
    *,
    safe_radius: int = 1,
    max_tries: int = 500,
    bomb_emoji: str = DEFAULT_BOMB_EMOJI,
) -> str:
    """size と bombs（爆弾個数）を指定して生成 + 推測不要（基本2規則）で解ける盤面のみ返す"""
    n = int(size)
    b = int(bombs)

    if n < 2:
        return "size は 2 以上にしてください。"

    safe = _make_safe_set(n, safe_radius)

    candidates = [(x, y) for x in range(n) for y in range(n) if (x, y) not in safe]
    max_bombs = len(candidates)

    if b < 0:
        return "bombs は 0 以上にしてください。"
    if b > max_bombs:
        return f"bombs が多すぎます。最大 {max_bombs}（safeエリア除外）です。"

    for _ in range(max_tries):
        grid = [[0 for _ in range(n)] for _ in range(n)]

        for (x, y) in random.sample(candidates, b):
            grid[x][y] = -1

        for x in range(n):
            for y in range(n):
                if grid[x][y] == -1:
                    continue
                cnt = 0
                for nx, ny in _neighbors(x, y):
                    if _in_bounds(n, nx, ny) and grid[nx][ny] == -1:
                        cnt += 1
                grid[x][y] = cnt

        if b > 0 and safe and all(grid[x][y] != 0 for (x, y) in safe):
            continue

        # 推測不要で解ける盤面のみ採用
        if not is_solvable_no_guess(grid, safe):
            continue

        header = f"[custom] size={n} bombs={b} safe_radius={max(0, int(safe_radius))}\n"
        text = _to_discord_text(grid, safe, header, bomb_emoji=bomb_emoji)

        if len(text) <= 2000:
            return text

    return "生成に失敗しました（推測不要盤面が見つかりません）。bombs を減らすか size を小さくして再試行してください。"
