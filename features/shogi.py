from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

SENTE = 1
GOTE = -1

PROMOTABLE = {"P", "L", "N", "S", "B", "R"}
HAND_ORDER = ["R", "B", "G", "S", "N", "L", "P"]


@dataclass
class Piece:
    owner: int
    kind: str
    promoted: bool = False


@dataclass
class PendingMove:
    from_x: int
    from_y: int
    to_x: int
    to_y: int


@dataclass
class ShogiGame:
    player_sente: int
    player_gote: int
    size: int = 9
    turn: int = SENTE
    finished: bool = False
    winner: Optional[int] = None
    last_move: Optional[tuple[int, int]] = None
    pending_move: Optional[PendingMove] = None
    board: list[list[Optional[Piece]]] = field(default_factory=list)
    hands: dict[int, dict[str, int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.board = [[None for _ in range(self.size)] for _ in range(self.size)]
        self.hands = {
            SENTE: {k: 0 for k in HAND_ORDER},
            GOTE: {k: 0 for k in HAND_ORDER},
        }
        self._init_standard_position()

    def _init_standard_position(self) -> None:
        # 先手を上側、後手を下側に置く（要件の成りゾーン: 先手7-9段, 後手1-3段 に合わせる）
        top = ["L", "N", "S", "G", "K", "G", "S", "N", "L"]
        bot = ["L", "N", "S", "G", "K", "G", "S", "N", "L"]
        for x, k in enumerate(top):
            self.board[0][x] = Piece(SENTE, k)
        self.board[1][1] = Piece(SENTE, "R")
        self.board[1][7] = Piece(SENTE, "B")
        for x in range(9):
            self.board[2][x] = Piece(SENTE, "P")

        for x in range(9):
            self.board[6][x] = Piece(GOTE, "P")
        self.board[7][1] = Piece(GOTE, "B")
        self.board[7][7] = Piece(GOTE, "R")
        for x, k in enumerate(bot):
            self.board[8][x] = Piece(GOTE, k)

    def current_player_id(self) -> int:
        return self.player_sente if self.turn == SENTE else self.player_gote

    def can_play(self, user_id: int) -> bool:
        return (not self.finished) and self.current_player_id() == user_id

    def status_line(self) -> str:
        if self.finished:
            if self.winner == SENTE:
                return "result: 先手勝ち"
            if self.winner == GOTE:
                return "result: 後手勝ち"
            return "result: 終了"
        return f"turn: {'先手' if self.turn == SENTE else '後手'}"

    def request_move(self, fx1: int, fy1: int, tx1: int, ty1: int, user_id: int) -> tuple[bool, str, bool]:
        if self.finished:
            return False, "この対局は既に終了しています。", False
        if self.pending_move is not None:
            return False, "まず y/n を答えてください。", False
        if not self.can_play(user_id):
            return False, "あなたの手番ではありません。", False

        fx, fy, tx, ty = fx1 - 1, fy1 - 1, tx1 - 1, ty1 - 1
        if not self._inside(fx, fy) or not self._inside(tx, ty):
            return False, "座標は 1..9 で指定してください。", False

        piece = self.board[fy][fx]
        if piece is None:
            return False, "移動元に駒がありません。", False
        if piece.owner != self.turn:
            return False, "自分の駒を動かしてください。", False
        if not self._can_piece_move(self.board, piece, fx, fy, tx, ty):
            return False, "その駒はその位置へ移動できません。", False

        dest = self.board[ty][tx]
        if dest is not None and dest.owner == self.turn:
            return False, "味方の駒があるマスには移動できません。", False

        forced = self._is_forced_promotion(piece, ty)
        promo_possible = self._is_promotion_possible(piece, fy, ty)
        if forced:
            return self._apply_move(fx, fy, tx, ty, promote=True)
        if promo_possible:
            self.pending_move = PendingMove(fx, fy, tx, ty)
            return True, "成りますか？ (y/n)", True
        return self._apply_move(fx, fy, tx, ty, promote=False)

    def confirm_pending(self, user_id: int, promote: bool) -> tuple[bool, str]:
        if self.pending_move is None:
            return False, "確認待ちの手はありません。"
        if not self.can_play(user_id):
            return False, "あなたの手番ではありません。"

        p = self.pending_move
        self.pending_move = None
        ok, msg, _ = self._apply_move(p.from_x, p.from_y, p.to_x, p.to_y, promote=promote)
        return ok, msg

    def request_drop(self, kind: str, tx1: int, ty1: int, user_id: int) -> tuple[bool, str, bool]:
        if self.finished:
            return False, "この対局は既に終了しています。", False
        if self.pending_move is not None:
            return False, "まず y/n を答えてください。", False
        if not self.can_play(user_id):
            return False, "あなたの手番ではありません。", False

        kind = kind.upper()
        tx, ty = tx1 - 1, ty1 - 1
        if kind not in {"P", "L", "N", "S", "G", "B", "R", "K"}:
            return False, "打ち駒は fu/kyou/kei/gin/kin/kaku/hisya/ou 形式で指定してください。", False
        if kind == "K":
            return False, "王(ou)は打てません。", False
        if not self._inside(tx, ty):
            return False, "座標は 1..9 で指定してください。", False
        if self.board[ty][tx] is not None:
            return False, "そのマスには駒があります。", False
        if self.hands[self.turn][kind] <= 0:
            return False, f"持ち駒に {kind} がありません。", False

        if kind == "P" and self._has_unpromoted_pawn_on_file(self.turn, tx):
            return False, "二歩です。", False

        if kind in {"P", "L"} and self._is_last_rank_for(self.turn, ty):
            return False, "その段には打てません。", False
        if kind == "N" and self._is_knight_dead_rank_for(self.turn, ty):
            return False, "その段には桂馬を打てません。", False

        # TODO: 打ち歩詰めは未実装
        ok, msg = self._apply_drop(kind, tx, ty)
        return ok, msg, False

    def _apply_move(self, fx: int, fy: int, tx: int, ty: int, promote: bool) -> tuple[bool, str, bool]:
        piece = self.board[fy][fx]
        assert piece is not None

        trial = self._clone_board(self.board)
        moving = trial[fy][fx]
        assert moving is not None
        captured = trial[ty][tx]
        trial[fy][fx] = None

        if promote and moving.kind in PROMOTABLE and not moving.promoted:
            moving.promoted = True
        trial[ty][tx] = moving

        if self._is_king_in_check_on_board(trial, moving.owner):
            return False, "王手放置はできません。", False

        self.board = trial
        if captured is not None:
            cap_kind = captured.kind
            self.hands[moving.owner][cap_kind] += 1
            if cap_kind == "K":
                self.finished = True
                self.winner = moving.owner

        self.last_move = (tx, ty)
        if not self.finished:
            self.turn *= -1
        return True, "OK", False

    def _apply_drop(self, kind: str, tx: int, ty: int) -> tuple[bool, str]:
        trial = self._clone_board(self.board)
        trial[ty][tx] = Piece(self.turn, kind, False)

        if self._is_king_in_check_on_board(trial, self.turn):
            return False, "王手放置はできません。"

        self.board = trial
        self.hands[self.turn][kind] -= 1
        self.last_move = (tx, ty)
        self.turn *= -1
        return True, "OK"

    def _is_promotion_possible(self, piece: Piece, from_y: int, to_y: int) -> bool:
        if piece.promoted or piece.kind not in PROMOTABLE:
            return False
        return self._in_promo_zone(piece.owner, from_y) or self._in_promo_zone(piece.owner, to_y)

    def _is_forced_promotion(self, piece: Piece, to_y: int) -> bool:
        if piece.promoted:
            return False
        if piece.kind in {"P", "L"}:
            return self._is_last_rank_for(piece.owner, to_y)
        if piece.kind == "N":
            return self._is_knight_dead_rank_for(piece.owner, to_y)
        return False

    def _in_promo_zone(self, owner: int, y: int) -> bool:
        # 入力段で: 先手 7-9段、後手 1-3段
        return y >= 6 if owner == SENTE else y <= 2

    def _is_last_rank_for(self, owner: int, y: int) -> bool:
        return y == 8 if owner == SENTE else y == 0

    def _is_knight_dead_rank_for(self, owner: int, y: int) -> bool:
        return y >= 7 if owner == SENTE else y <= 1

    def _has_unpromoted_pawn_on_file(self, owner: int, x: int) -> bool:
        for y in range(self.size):
            p = self.board[y][x]
            if p and p.owner == owner and p.kind == "P" and not p.promoted:
                return True
        return False

    def _is_king_in_check_on_board(self, board: list[list[Optional[Piece]]], owner: int) -> bool:
        king_pos = self._find_king(board, owner)
        if king_pos is None:
            return True
        kx, ky = king_pos
        return self._is_square_attacked(board, kx, ky, -owner)

    def _find_king(self, board: list[list[Optional[Piece]]], owner: int) -> Optional[tuple[int, int]]:
        for y in range(self.size):
            for x in range(self.size):
                p = board[y][x]
                if p and p.owner == owner and p.kind == "K":
                    return x, y
        return None

    def _is_square_attacked(self, board: list[list[Optional[Piece]]], tx: int, ty: int, attacker: int) -> bool:
        for y in range(self.size):
            for x in range(self.size):
                p = board[y][x]
                if p and p.owner == attacker:
                    if self._can_piece_move(board, p, x, y, tx, ty):
                        return True
        return False

    def _inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.size and 0 <= y < self.size

    def _can_piece_move(
        self,
        board: list[list[Optional[Piece]]],
        piece: Piece,
        fx: int,
        fy: int,
        tx: int,
        ty: int,
    ) -> bool:
        if fx == tx and fy == ty:
            return False
        if not self._inside(tx, ty):
            return False
        dest = board[ty][tx]
        if dest is not None and dest.owner == piece.owner:
            return False

        dx = tx - fx
        dy = ty - fy
        step = 1 if piece.owner == SENTE else -1

        if piece.kind == "K":
            return abs(dx) <= 1 and abs(dy) <= 1

        if piece.promoted and piece.kind in {"P", "L", "N", "S"}:
            return self._is_gold_move(dx, dy, step)

        if piece.kind == "G":
            return self._is_gold_move(dx, dy, step)

        if piece.kind == "S":
            return (dx, dy) in {(0, step), (-1, step), (1, step), (-1, -step), (1, -step)}

        if piece.kind == "N":
            return (dx, dy) in {(-1, 2 * step), (1, 2 * step)}

        if piece.kind == "L":
            return dx == 0 and self._is_clear_line(board, fx, fy, tx, ty)

        if piece.kind == "P":
            return dx == 0 and dy == step

        if piece.kind == "B":
            diag = abs(dx) == abs(dy) and self._is_clear_line(board, fx, fy, tx, ty)
            if piece.promoted:
                return diag or (abs(dx) == 1 and abs(dy) == 0) or (abs(dx) == 0 and abs(dy) == 1)
            return diag

        if piece.kind == "R":
            straight = (dx == 0 or dy == 0) and self._is_clear_line(board, fx, fy, tx, ty)
            if piece.promoted:
                return straight or (abs(dx) == 1 and abs(dy) == 1)
            return straight

        return False

    def _is_gold_move(self, dx: int, dy: int, step: int) -> bool:
        return (dx, dy) in {
            (0, step),
            (-1, step),
            (1, step),
            (-1, 0),
            (1, 0),
            (0, -step),
        }

    def _is_clear_line(
        self,
        board: list[list[Optional[Piece]]],
        fx: int,
        fy: int,
        tx: int,
        ty: int,
    ) -> bool:
        dx = tx - fx
        dy = ty - fy
        step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
        step_y = 0 if dy == 0 else (1 if dy > 0 else -1)

        if not (dx == 0 or dy == 0 or abs(dx) == abs(dy)):
            return False

        cx, cy = fx + step_x, fy + step_y
        while cx != tx or cy != ty:
            if board[cy][cx] is not None:
                return False
            cx += step_x
            cy += step_y
        return True

    def _clone_board(self, board: list[list[Optional[Piece]]]) -> list[list[Optional[Piece]]]:
        new_board: list[list[Optional[Piece]]] = []
        for row in board:
            new_row: list[Optional[Piece]] = []
            for p in row:
                if p is None:
                    new_row.append(None)
                else:
                    new_row.append(Piece(p.owner, p.kind, p.promoted))
            new_board.append(new_row)
        return new_board
