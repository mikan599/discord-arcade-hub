from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from features.shogi import ShogiGame, Piece, SENTE, GOTE, HAND_ORDER

KANJI = {
    "P": "歩",
    "L": "香",
    "N": "桂",
    "S": "銀",
    "G": "金",
    "B": "角",
    "R": "飛",
    "K": "王",
}

PROMOTED_KANJI = {
    "P": "と",
    "L": "杏",
    "N": "圭",
    "S": "全",
    "B": "馬",
    "R": "龍",
}


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "NotoSansCJK-Regular.ttc",
        "NotoSansJP-Regular.otf",
        "meiryo.ttc",
        "msgothic.ttc",
        "arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _piece_label(piece: Piece) -> str:
    if piece.promoted and piece.kind in PROMOTED_KANJI:
        return PROMOTED_KANJI[piece.kind]
    return KANJI[piece.kind]


def render_shogi_png(game: ShogiGame) -> BytesIO:
    cell = 72
    margin = 120
    side_w = 220
    status_h = 84

    board_px = 9 * cell
    left = side_w + margin
    top = margin
    right = left + board_px
    bottom = top + board_px

    width = side_w * 2 + margin * 2 + board_px
    height = margin * 2 + board_px + status_h

    img = Image.new("RGBA", (width, height), (243, 224, 168, 255))
    d = ImageDraw.Draw(img)

    font_coord = _load_font(34)
    font_piece = _load_font(44)
    font_hand = _load_font(30)
    font_status = _load_font(30)

    # 盤
    d.rectangle([left, top, right, bottom], outline=(50, 40, 20, 255), width=3)
    for i in range(1, 9):
        x = left + i * cell
        y = top + i * cell
        d.line([x, top, x, bottom], fill=(70, 58, 30, 255), width=2)
        d.line([left, y, right, y], fill=(70, 58, 30, 255), width=2)

    for i in range(9):
        txt = str(i + 1)
        tw = d.textlength(txt, font=font_coord)
        d.text((left + i * cell + (cell - tw) / 2, top - 52), txt, fill=(20, 20, 20, 255), font=font_coord)
        d.text((left - 42, top + i * cell + 14), txt, fill=(20, 20, 20, 255), font=font_coord)

    if game.last_move:
        lx, ly = game.last_move
        d.rectangle(
            [left + lx * cell + 3, top + ly * cell + 3, left + (lx + 1) * cell - 3, top + (ly + 1) * cell - 3],
            outline=(220, 40, 40, 255),
            width=5,
        )

    for y in range(9):
        for x in range(9):
            piece = game.board[y][x]
            if piece is None:
                continue
            label = _piece_label(piece)
            px = left + x * cell + 12
            py = top + y * cell + 10

            if piece.owner == SENTE:
                d.text((px, py), label, fill=(10, 10, 10, 255), font=font_piece)
            else:
                tile = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
                td = ImageDraw.Draw(tile)
                td.text((12, 10), label, fill=(10, 10, 10, 255), font=font_piece)
                tile = tile.rotate(180)
                img.alpha_composite(tile, dest=(left + x * cell, top + y * cell))

    # 持ち駒
    def hand_text(owner: int) -> str:
        parts = []
        for k in HAND_ORDER:
            cnt = game.hands[owner][k]
            if cnt > 0:
                parts.append(f"{KANJI[k]}x{cnt}")
        return " ".join(parts) if parts else "なし"

    d.text((42, top + 8), "先手持ち駒", fill=(15, 15, 15, 255), font=font_hand)
    d.multiline_text((42, top + 56), hand_text(SENTE), fill=(25, 25, 25, 255), font=font_hand, spacing=10)

    d.text((right + 42, top + 8), "後手持ち駒", fill=(15, 15, 15, 255), font=font_hand)
    d.multiline_text((right + 42, top + 56), hand_text(GOTE), fill=(25, 25, 25, 255), font=font_hand, spacing=10)

    d.text((left, bottom + 20), game.status_line(), fill=(10, 10, 10, 255), font=font_status)

    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
