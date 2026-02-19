from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Optional, Tuple, List, Iterable, Set

EMPTY = 0
X = 1  # 先手（黒）
O = 2  # 後手（白）


def _inside(n: int, x: int, y: int) -> bool:
    return 0 <= x < n and 0 <= y < n


@dataclass
class GomokuGame:
    size: int
    mode: str  # "pvp" or "ai"
    player_x: Optional[int]  # X担当ユーザーID（AIならNone）
    player_o: Optional[int]  # O担当ユーザーID（AIならNone）
    ai_level: Optional[str] = None  # "easy"/"normal"/"hard"
    turn: int = X
    finished: bool = False
    winner: Optional[int] = None  # X/O
    last_move: Optional[Tuple[int, int]] = None  # 0-index (x,y)

    def __post_init__(self):
        self.board: List[List[int]] = [[EMPTY for _ in range(self.size)] for _ in range(self.size)]

    # ---------------- common ----------------

    def current_player_id(self) -> Optional[int]:
        return self.player_x if self.turn == X else self.player_o

    def can_play(self, user_id: int) -> bool:
        if self.finished:
            return False
        pid = self.current_player_id()
        return pid is not None and pid == user_id

    def is_ai_turn(self) -> bool:
        if self.finished:
            return False
        pid = self.current_player_id()
        return pid is None  # None ならAI

    def status_line(self) -> str:
        if self.finished:
            if self.winner == X:
                return "result: Black wins"
            if self.winner == O:
                return "result: White wins"
            return "result: draw"
        return f"turn: {'Black' if self.turn == X else 'White'}"

    def place(self, x1: int, y1: int, user_id: int) -> Tuple[bool, str]:
        """
        x1,y1: 1-indexed input
        returns: (ok, message)
        """
        if self.finished:
            return False, "この対局は既に終了しています。"

        if not self.can_play(user_id):
            return False, "あなたの手番ではありません。"

        x = x1 - 1
        y = y1 - 1
        if not _inside(self.size, x, y):
            return False, f"範囲外です。1〜{self.size}で指定してください。"
        if self.board[y][x] != EMPTY:
            return False, "そこには既に石があります。"

        ok, msg = self._place_with_rules(x, y, self.turn)
        return ok, msg

    def _place_raw(self, x: int, y: int, who: int) -> None:
        """内部用：合法性チェックなしで置く（bot側が合法手だけ呼ぶこと）"""
        self.board[y][x] = who
        self.last_move = (x, y)

        if who == X:
            if self._is_exact_five_from(x, y, who=X):
                self.finished = True
                self.winner = X
                return
        else:
            if self._is_five_or_more_from(x, y, who=O):
                self.finished = True
                self.winner = O
                return

        if self._is_draw():
            self.finished = True
            self.winner = None
            return

        self.turn = O if who == X else X

    def _is_draw(self) -> bool:
        return all(self.board[yy][xx] != EMPTY for yy in range(self.size) for xx in range(self.size))

    # ---------------- rules (Renju-like for X only) ----------------
    # 先手(X)のみ禁じ手: 33/44/長連（6以上）
    # 勝ち: Xは「ちょうど5」、Oは「5以上」

    def _place_with_rules(self, x: int, y: int, who: int) -> Tuple[bool, str]:
        self.board[y][x] = who
        self.last_move = (x, y)

        if who == O:
            if self._is_five_or_more_from(x, y, who=O):
                self.finished = True
                self.winner = O
                return True, "勝敗が決まりました。"
            if self._is_draw():
                self.finished = True
                self.winner = None
                return True, "勝敗が決まりました。"
            self.turn = X
            return True, "OK"

        # who == X (forbidden)
        if self._creates_overline(x, y, who=X):
            self.board[y][x] = EMPTY
            self.last_move = None
            return False, "禁じ手: 長連（6以上）が発生します。"

        # ちょうど5なら勝ち（禁じ手より勝ちを優先）
        if self._is_exact_five_from(x, y, who=X):
            self.finished = True
            self.winner = X
            return True, "勝敗が決まりました。"

        if self._is_forbidden_44(x, y):
            self.board[y][x] = EMPTY
            self.last_move = None
            return False, "禁じ手: 四四（同時に2つ以上の四の筋）が発生します。"

        if self._is_forbidden_33(x, y):
            self.board[y][x] = EMPTY
            self.last_move = None
            return False, "禁じ手: 三三（同時に2つ以上の両開き三）が発生します。"

        if self._is_draw():
            self.finished = True
            self.winner = None
            return True, "勝敗が決まりました。"

        self.turn = O
        return True, "OK"

    # ---------------- win checks ----------------

    def _count_one_dir(self, x: int, y: int, dx: int, dy: int, who: int) -> int:
        cnt = 0
        cx, cy = x + dx, y + dy
        while _inside(self.size, cx, cy) and self.board[cy][cx] == who:
            cnt += 1
            cx += dx
            cy += dy
        return cnt

    def _max_run_in_dir(self, x: int, y: int, dx: int, dy: int, who: int) -> int:
        return 1 + self._count_one_dir(x, y, dx, dy, who) + self._count_one_dir(x, y, -dx, -dy, who)

    def _is_five_or_more_from(self, x: int, y: int, who: int) -> bool:
        for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
            if self._max_run_in_dir(x, y, dx, dy, who) >= 5:
                return True
        return False

    def _is_exact_five_from(self, x: int, y: int, who: int) -> bool:
        for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
            if self._max_run_in_dir(x, y, dx, dy, who) == 5:
                return True
        return False

    def _creates_overline(self, x: int, y: int, who: int) -> bool:
        for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
            if self._max_run_in_dir(x, y, dx, dy, who) >= 6:
                return True
        return False

    # ---------------- forbidden detection (practical approximation) ----------------

    def _line_string(self, x: int, y: int, dx: int, dy: int, span: int = 6) -> Tuple[str, int]:
        chars = []
        for k in range(-span, span + 1):
            cx, cy = x + dx * k, y + dy * k
            if not _inside(self.size, cx, cy):
                chars.append("#")
            else:
                v = self.board[cy][cx]
                if v == EMPTY:
                    chars.append(".")
                elif v == X:
                    chars.append("X")
                else:
                    chars.append("O")
        return "".join(chars), span

    def _has_open_three_in_dir_involving_center(self, x: int, y: int, dx: int, dy: int) -> bool:
        line, c = self._line_string(x, y, dx, dy, span=6)
        patterns = [
            ".XXX.",
            ".XX.X.",
            ".X.XX.",
        ]
        for p in patterns:
            start = 0
            while True:
                idx = line.find(p, start)
                if idx == -1:
                    break
                end = idx + len(p)
                if idx <= c < end and "#" not in line[idx:end]:
                    return True
                start = idx + 1
        return False

    def _winning_cells_in_dir_for_x(self, x: int, y: int, dx: int, dy: int) -> int:
        candidates: List[Tuple[int, int]] = []
        for k in range(-5, 6):
            cx, cy = x + dx * k, y + dy * k
            if _inside(self.size, cx, cy) and self.board[cy][cx] == EMPTY:
                candidates.append((cx, cy))

        cnt = 0
        for cx, cy in candidates:
            self.board[cy][cx] = X
            is_win = self._is_exact_five_from(cx, cy, who=X) and (not self._creates_overline(cx, cy, who=X))
            self.board[cy][cx] = EMPTY
            if is_win:
                cnt += 1
        return cnt

    def _is_forbidden_44(self, x: int, y: int) -> bool:
        four_dirs = 0
        for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
            if self._winning_cells_in_dir_for_x(x, y, dx, dy) >= 1:
                four_dirs += 1
        return four_dirs >= 2

    def _is_forbidden_33(self, x: int, y: int) -> bool:
        three_dirs = 0
        for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
            if self._has_open_three_in_dir_involving_center(x, y, dx, dy):
                three_dirs += 1
        return three_dirs >= 2

    def is_legal_move(self, x: int, y: int, who: int) -> bool:
        """AI探索用：その手が合法か（禁じ手込み）"""
        if not _inside(self.size, x, y):
            return False
        if self.board[y][x] != EMPTY:
            return False

        self.board[y][x] = who
        ok = True

        if who == X:
            if self._creates_overline(x, y, who=X):
                ok = False
            elif self._is_forbidden_44(x, y):
                ok = False
            elif self._is_forbidden_33(x, y):
                ok = False

        self.board[y][x] = EMPTY
        return ok

    # ---------------- AI (Route B) ----------------

    def ai_move(self) -> Tuple[int, int]:
        """AIの番（player_id が None の側）で呼ぶ。戻り値は0-index(x,y)"""
        if not self.is_ai_turn():
            raise RuntimeError("ai_move called but it's not AI turn")

        lvl = (self.ai_level or "easy").lower()
        who = self.turn
        if lvl == "hard":
            # ここを上げると強くなるが重くなる
            return self._ai_move_hard(who, depth=2, radius=2, candidate_limit=40)
        if lvl == "normal":
            return self._ai_move_normal(who)
        return self._ai_move_easy(who)

    def _opponent(self, who: int) -> int:
        return O if who == X else X

    def _is_win_if_put(self, x: int, y: int, who: int) -> bool:
        self.board[y][x] = who
        win = False
        if who == X:
            win = self._is_exact_five_from(x, y, who=X) and (not self._creates_overline(x, y, who=X))
        else:
            win = self._is_five_or_more_from(x, y, who=O)
        self.board[y][x] = EMPTY
        return win

    # ---- immediate win / block ----

    def _find_immediate_win(self, who: int) -> Optional[Tuple[int, int]]:
        for y in range(self.size):
            for x in range(self.size):
                if self.board[y][x] != EMPTY:
                    continue
                if who == X and not self.is_legal_move(x, y, X):
                    continue
                if self._is_win_if_put(x, y, who):
                    return (x, y)
        return None

    def _find_immediate_block(self, who: int) -> Optional[Tuple[int, int]]:
        """相手の即勝ちを塞ぐ（相手がその手を合法に打てる場合のみ脅威扱い）"""
        opp = self._opponent(who)
        for y in range(self.size):
            for x in range(self.size):
                if self.board[y][x] != EMPTY:
                    continue
                if opp == X and not self.is_legal_move(x, y, X):
                    continue
                if self._is_win_if_put(x, y, opp):
                    if who == X and not self.is_legal_move(x, y, X):
                        continue
                    return (x, y)
        return None

    # ---- fork (four+three etc) detection: "after 1 move, next has >=2 immediate wins" ----

    def _threat_candidates(self, who: int, *, radius: int = 3) -> List[Tuple[int, int]]:
        """
        fork判定など、少し広めに候補を集めたいとき用。
        盤上の石の周辺（radius）+ 空点のみ。
        """
        n = self.size
        stones = [(x, y) for y in range(n) for x in range(n) if self.board[y][x] != EMPTY]
        if not stones:
            c = n // 2
            return [(c, c)]

        cand: Set[Tuple[int, int]] = set()
        for sx, sy in stones:
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = sx + dx, sy + dy
                    if _inside(n, nx, ny) and self.board[ny][nx] == EMPTY:
                        cand.add((nx, ny))

        out: List[Tuple[int, int]] = []
        for x, y in cand:
            if who == X and not self.is_legal_move(x, y, X):
                continue
            out.append((x, y))
        return out

    def _count_immediate_wins(self, who: int, *, early_stop: int = 2) -> int:
        """
        現局面で、who が次の1手で勝てる手の個数（早期打ち切りあり）
        """
        cnt = 0
        for y in range(self.size):
            for x in range(self.size):
                if self.board[y][x] != EMPTY:
                    continue
                if who == X and not self.is_legal_move(x, y, X):
                    continue
                if self._is_win_if_put(x, y, who):
                    cnt += 1
                    if cnt >= early_stop:
                        return cnt
        return cnt

    def _is_fork_move(self, x: int, y: int, who: int) -> bool:
        """
        who が (x,y) に打つと、次に who の即勝ち手が2つ以上生えるか？
        """
        if self.board[y][x] != EMPTY:
            return False
        if who == X and not self.is_legal_move(x, y, X):
            return False

        self.board[y][x] = who
        ok = self._count_immediate_wins(who, early_stop=2) >= 2
        self.board[y][x] = EMPTY
        return ok

    def _find_fork_moves(self, who: int) -> List[Tuple[int, int]]:
        """
        who にとって fork になる手を列挙（近傍に限定してコストを抑える）
        """
        moves = []
        for x, y in self._threat_candidates(who, radius=3):
            if self._is_fork_move(x, y, who):
                moves.append((x, y))
        return moves

    def _find_fork_block(self, who: int) -> Optional[Tuple[int, int]]:
        """
        相手の fork を未然に防ぐ最優先ブロック。
        相手の fork 手そのものを埋める（=相手に打たせない）。
        """
        opp = self._opponent(who)
        forks = self._find_fork_moves(opp)
        if not forks:
            return None

        # 複数あるなら、自分にとって一番マシな手を返す
        best = None
        best_s = -(10**18)
        for x, y in forks:
            if self.board[y][x] != EMPTY:
                continue
            if who == X and not self.is_legal_move(x, y, X):
                continue
            s = self._eval_move(x, y, who)
            if s > best_s:
                best_s = s
                best = (x, y)
        return best

    # ---- move candidates & eval ----

    def _candidate_moves_near(
        self,
        *,
        radius: int,
        limit: int,
        who: int,
        forced: Iterable[Tuple[int, int]] = (),
    ) -> List[Tuple[int, int]]:
        """
        探索用候補生成。
        - 近傍に限定
        - 評価上位 limit に絞る
        - forced（防御必須など）は limit で落とさない
        """
        n = self.size
        stones = [(x, y) for y in range(n) for x in range(n) if self.board[y][x] != EMPTY]
        if not stones:
            c = n // 2
            return [(c, c)]

        cand: Set[Tuple[int, int]] = set()

        # forced を先に入れる
        for fx, fy in forced:
            if _inside(n, fx, fy) and self.board[fy][fx] == EMPTY:
                if who == X and not self.is_legal_move(fx, fy, X):
                    continue
                cand.add((fx, fy))

        # 近傍
        for sx, sy in stones:
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = sx + dx, sy + dy
                    if _inside(n, nx, ny) and self.board[ny][nx] == EMPTY:
                        cand.add((nx, ny))

        legal: List[Tuple[int, int]] = []
        for x, y in cand:
            if who == X and not self.is_legal_move(x, y, X):
                continue
            legal.append((x, y))

        if not legal:
            return []

        # forced を落とさず、それ以外を評価で上位 limit にする
        forced_set = set(forced)
        must_keep = [m for m in legal if m in forced_set]
        rest = [m for m in legal if m not in forced_set]

        scored = [(self._eval_move(x, y, who), x, y) for (x, y) in rest]
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[: max(0, limit - len(must_keep))]
        merged = must_keep + [(x, y) for _, x, y in top]

        # 念のため重複除去
        out: List[Tuple[int, int]] = []
        seen = set()
        for m in merged:
            if m not in seen:
                out.append(m)
                seen.add(m)
        return out

    def _line_features_if_put(self, x: int, y: int, who: int, dx: int, dy: int) -> Tuple[int, int]:
        """
        (x,y)にwhoを置いたと仮定したとき、その方向の
        - 連の長さ
        - open ends（0/1/2）
        を返す
        """
        n = self.size

        def walk(stepx, stepy):
            cnt = 0
            cx, cy = x + stepx, y + stepy
            while _inside(n, cx, cy) and self.board[cy][cx] == who:
                cnt += 1
                cx += stepx
                cy += stepy
            open_end = 1 if (_inside(n, cx, cy) and self.board[cy][cx] == EMPTY) else 0
            return cnt, open_end

        c1, o1 = walk(dx, dy)
        c2, o2 = walk(-dx, -dy)
        length = 1 + c1 + c2
        return length, (o1 + o2)

    def _eval_move(self, x: int, y: int, who: int) -> int:
        """候補手の静的評価（Route B用のベース）"""
        if self.board[y][x] != EMPTY:
            return -10**9
        if who == X and not self.is_legal_move(x, y, X):
            return -10**9

        opp = self._opponent(who)

        # 勝ち/即負けブロックを最優先
        if self._is_win_if_put(x, y, who):
            return 10**8
        if (opp == X and self.is_legal_move(x, y, X) or opp == O) and self._is_win_if_put(x, y, opp):
            return 9 * 10**7

        dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]

        def score_for(p: int) -> int:
            s = 0
            for dx, dy in dirs:
                length, open_ends = self._line_features_if_put(x, y, p, dx, dy)

                if p == O:
                    if length >= 5:
                        s += 1_000_000
                    elif length == 4:
                        s += 120_000 if open_ends == 2 else (30_000 if open_ends == 1 else 0)
                    elif length == 3:
                        s += 12_000 if open_ends == 2 else (3_000 if open_ends == 1 else 0)
                    elif length == 2:
                        s += 1_200 if open_ends == 2 else (300 if open_ends == 1 else 0)
                else:
                    if length >= 5:
                        s += 800_000
                    elif length == 4:
                        s += 110_000 if open_ends == 2 else (25_000 if open_ends == 1 else 0)
                    elif length == 3:
                        s += 11_000 if open_ends == 2 else (2_500 if open_ends == 1 else 0)
                    elif length == 2:
                        s += 1_000 if open_ends == 2 else (250 if open_ends == 1 else 0)
            return s

        attack = score_for(who)
        defense = score_for(opp)

        # 中央寄せ（序盤）
        cx = cy = (self.size - 1) / 2.0
        dist = abs(x - cx) + abs(y - cy)
        center_bonus = int(120 - dist * 6)

        return attack + int(defense * 0.95) + center_bonus

    def _static_eval_board(self, who: int) -> int:
        """盤面全体評価（探索の葉）"""
        n = self.size
        near = set()
        for y in range(n):
            for x in range(n):
                if self.board[y][x] == EMPTY:
                    continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if _inside(n, nx, ny) and self.board[ny][nx] == EMPTY:
                            near.add((nx, ny))

        if not near:
            c = n // 2
            return 0 if (self.board[c][c] != EMPTY) else 50

        opp = self._opponent(who)
        best_who = -(10**18)
        best_opp = -(10**18)
        for x, y in near:
            if who == X and not self.is_legal_move(x, y, X):
                continue
            best_who = max(best_who, self._eval_move(x, y, who))
        for x, y in near:
            if opp == X and not self.is_legal_move(x, y, X):
                continue
            best_opp = max(best_opp, self._eval_move(x, y, opp))
        return int(best_who - best_opp * 0.92)

    # ---------------- AI levels ----------------

    def _ai_move_easy(self, who: int) -> Tuple[int, int]:
        win = self._find_immediate_win(who)
        if win:
            return win
        block = self._find_immediate_block(who)
        if block:
            return block

        moves = self._candidate_moves_near(radius=2, limit=18, who=who)
        return random.choice(moves) if moves else (self.size // 2, self.size // 2)

    def _ai_move_normal(self, who: int) -> Tuple[int, int]:
        win = self._find_immediate_win(who)
        if win:
            return win
        block = self._find_immediate_block(who)
        if block:
            return block

        # forkブロック（normalにも少しだけ効かせる）
        fork_block = self._find_fork_block(who)
        if fork_block:
            return fork_block

        moves = self._candidate_moves_near(radius=2, limit=20, who=who)
        if not moves:
            return (self.size // 2, self.size // 2)

        scored = [(self._eval_move(x, y, who), x, y) for (x, y) in moves]
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[: min(6, len(scored))]
        _, x, y = random.choice(top)
        return (x, y)

    def _ai_move_hard(self, who: int, *, depth: int, radius: int, candidate_limit: int) -> Tuple[int, int]:
        """
        hard:
        1) 即勝ち
        2) 即負けブロック
        3) fork（四三などの「次に勝ち手が2つ以上」）ブロック
        4) 自分のforkがあれば作る
        5) alpha-beta
        """
        opp = self._opponent(who)

        win = self._find_immediate_win(who)
        if win:
            return win

        block = self._find_immediate_block(who)
        if block:
            return block

        # ここが今回の「決定的な弱さ」を潰す核
        fork_block = self._find_fork_block(who)
        if fork_block:
            return fork_block

        # 逆に自分がforkを作れるなら強い（禁じ手は is_legal_move で弾かれる）
        my_forks = self._find_fork_moves(who)
        if my_forks:
            # 一番良さそうなのを選ぶ
            best = max(my_forks, key=lambda m: self._eval_move(m[0], m[1], who))
            return best

        # forcedとして「forkブロック候補」や「相手の即勝ち点」も混ぜて、候補から落ちないようにする
        forced: List[Tuple[int, int]] = []

        # 相手の即勝ち点（複数ある場合）を forced に入れて、候補落ちを防ぐ
        for y in range(self.size):
            for x in range(self.size):
                if self.board[y][x] != EMPTY:
                    continue
                if opp == X and not self.is_legal_move(x, y, X):
                    continue
                if self._is_win_if_put(x, y, opp):
                    forced.append((x, y))

        moves = self._candidate_moves_near(radius=radius, limit=candidate_limit, who=who, forced=forced)
        if not moves:
            return self._ai_move_normal(who)

        def negamax(turn: int, d: int, alpha: int, beta: int) -> int:
            if self.finished:
                if self.winner == who:
                    return 10**9
                if self.winner == opp:
                    return -(10**9)
                return 0

            if d == 0:
                return self._static_eval_board(who)

            cand = self._candidate_moves_near(radius=radius, limit=candidate_limit, who=turn)
            if not cand:
                return 0

            best = -(10**18)
            for mx, my in cand:
                self.board[my][mx] = turn
                prev_last = self.last_move
                self.last_move = (mx, my)

                ended = False
                prev_finished = self.finished
                prev_winner = self.winner

                if turn == X:
                    if self._is_exact_five_from(mx, my, who=X):
                        self.finished = True
                        self.winner = X
                        ended = True
                else:
                    if self._is_five_or_more_from(mx, my, who=O):
                        self.finished = True
                        self.winner = O
                        ended = True

                if ended:
                    val = 10**9 if turn == who else -(10**9)
                else:
                    val = -negamax(self._opponent(turn), d - 1, -beta, -alpha)

                self.board[my][mx] = EMPTY
                self.last_move = prev_last
                self.finished = prev_finished
                self.winner = prev_winner

                if val > best:
                    best = val
                if best > alpha:
                    alpha = best
                if alpha >= beta:
                    break

            return int(best)

        best_move = moves[0]
        best_val = -(10**18)

        for x, y in moves:
            self.board[y][x] = who
            prev_last = self.last_move
            self.last_move = (x, y)

            # 即勝ち（念のため）
            if (who == X and self._is_exact_five_from(x, y, who=X)) or (who == O and self._is_five_or_more_from(x, y, who=O)):
                self.board[y][x] = EMPTY
                self.last_move = prev_last
                return (x, y)

            val = -negamax(opp, depth - 1, -(10**18), 10**18)

            self.board[y][x] = EMPTY
            self.last_move = prev_last

            if val > best_val:
                best_val = val
                best_move = (x, y)

        return best_move
