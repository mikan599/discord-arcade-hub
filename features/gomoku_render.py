from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from features.gomoku import EMPTY, X, O, GomokuGame


def _load_font(size: int) -> ImageFont.ImageFont:
    """
    環境差があるので、よくあるフォントを順番に試す。
    見つからなければデフォルトフォント（小さい）になる。
    """
    candidates = [
        "arial.ttf",                 # Windowsでよくある
        "meiryo.ttc",                # 日本語環境
        "msgothic.ttc",              # 日本語環境
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def render_gomoku_png(
    game: GomokuGame,
    *,
    cell: int = 56,      # 交点間の距離（少し大きめ）
    margin: int = 80,    # ラベル用余白（少し大きめ）
) -> BytesIO:
    """
    五目盤面をPNGで生成して BytesIO を返す。
    - 交点上に石を置く（升目中心ではない）
    - 上と左に座標ラベル
    - 最終手を赤枠でハイライト
    """
    n = game.size

    # 盤面は「n本の線」= 交点は n×n、全長は (n-1)*cell
    board_px = (n - 1) * cell
    left = margin
    top = margin
    right = left + board_px
    bottom = top + board_px

    # 下にステータス欄
    status_h = 56

    w = margin * 2 + board_px
    h = margin * 2 + board_px + status_h

    # 背景（将棋盤っぽい色）
    img = Image.new("RGBA", (w, h), (245, 236, 210, 255))
    d = ImageDraw.Draw(img)

    # フォント（数字は見やすく2倍くらいに）
    font_label = _load_font(28)   # ←大きく
    font_status = _load_font(26)  # ←大きく

    # 線の色
    line_color = (70, 70, 70, 255)

    # n本の縦線・横線（交点式）
    for i in range(n):
        x = left + i * cell
        y = top + i * cell
        d.line([x, top, x, bottom], fill=line_color, width=2)
        d.line([left, y, right, y], fill=line_color, width=2)

    # 交点座標
    def pt(ix: int, iy: int) -> tuple[int, int]:
        return (left + ix * cell, top + iy * cell)

    # 座標ラベル（上と左）
    # 上: x位置に合わせて、上に配置
    # 左: y位置に合わせて、左に配置
    for i in range(n):
        label = str(i + 1)

        # 上
        x, _ = pt(i, 0)
        # 文字幅に応じて中央寄せ（ざっくり）
        tw = d.textlength(label, font=font_label)
        d.text((x - tw / 2, top - 52), label, fill=(15, 15, 15, 255), font=font_label)

        # 左
        _, y = pt(0, i)
        tw = d.textlength(label, font=font_label)
        d.text((left - 52 - tw / 2, y - 18), label, fill=(15, 15, 15, 255), font=font_label)

    # 石（交点上）
    # cellに対して半径を決める（線が見えるように少し小さめ）
    radius = int(cell * 0.42)

    last = game.last_move  # (x,y) 0-index

    for y in range(n):
        for x in range(n):
            v = game.board[y][x]
            if v == EMPTY:
                continue

            cx, cy = pt(x, y)
            bbox = [cx - radius, cy - radius, cx + radius, cy + radius]

            if v == X:
                fill = (25, 25, 25, 255)
                outline = (10, 10, 10, 255)
            else:
                fill = (250, 250, 250, 255)
                outline = (30, 30, 30, 255)

            d.ellipse(bbox, fill=fill, outline=outline, width=3)

            # 最終手ハイライト（赤リング）
            if last and (x, y) == last:
                hl = [cx - radius - 6, cy - radius - 6, cx + radius + 6, cy + radius + 6]
                d.ellipse(hl, outline=(220, 40, 40, 255), width=5)

    # ステータス
    status = game.status_line()
    d.text((margin, bottom + 12), status, fill=(10, 10, 10, 255), font=font_status)

    # 出力
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
