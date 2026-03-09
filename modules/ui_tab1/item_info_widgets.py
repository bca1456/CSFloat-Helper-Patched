# modules/ui_tab1/item_info_widgets.py

import math
import re
import statistics
from datetime import datetime, timedelta, timezone

from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QToolTip
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QPainterPath, QBrush, QPixmap
from PyQt6.QtCore import Qt, QPointF, QRectF, QRect

from modules.theme import Theme
from modules.utils import cents_to_dollars, format_date
from modules.ui_tab1.constants import RARITY_NAMES


# ═══════════════════════════════════════════════════════════════════
# Stats settings + calculation helpers
# ═══════════════════════════════════════════════════════════════════

STATS_SETTINGS_KEYS = {
    "score": "stats_score_metric",
    "price": "stats_price_metric",
    "volume": "stats_volume_metric",
    "volatility": "stats_volatility_metric",
}


def filter_by_days(graph, days):
    """Фильтрует записи графика по календарным дням от сегодня."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    result = []
    for d in graph:
        try:
            dt = datetime.fromisoformat(d["day"].replace("Z", "+00:00")).date()
            if dt >= cutoff:
                result.append(d)
        except Exception:
            continue
    return result


def _clean_prices(prices):
    """IQR-фильтрация выбросов. Возвращает цены без аномалий."""
    if len(prices) < 4:
        return prices
    sorted_p = sorted(prices)
    n = len(sorted_p)
    q1 = sorted_p[n // 4]
    q3 = sorted_p[3 * n // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    cleaned = [p for p in prices if lower <= p <= upper]
    return cleaned if cleaned else prices


def calc_price(data, metric):
    raw_prices = [d["avg_price"] for d in data]
    prices = _clean_prices(raw_prices)
    if metric == "average":
        return statistics.mean(prices) / 100
    if metric == "min":
        return min(prices) / 100
    if metric == "max":
        return max(prices) / 100
    if metric == "weighted":
        sorted_p = sorted(raw_prices)
        n = len(sorted_p)
        if n >= 4:
            q1, q3 = sorted_p[n // 4], sorted_p[3 * n // 4]
            upper = q3 + 1.5 * (q3 - q1)
            filtered = [(d["avg_price"], d["count"]) for d in data if d["avg_price"] <= upper]
        else:
            filtered = [(d["avg_price"], d["count"]) for d in data]
        total_vol = sum(c for _, c in filtered)
        if total_vol == 0:
            return statistics.median(prices) / 100
        return sum(p * c for p, c in filtered) / total_vol / 100
    return statistics.median(prices) / 100


def calc_volume(data, days, metric):
    total = sum(d["count"] for d in data)
    if metric == "avg_day":
        return round(total / days, 1) if days else 0
    if metric == "med_day":
        daily = [d["count"] for d in data]
        return round(statistics.median(daily), 1) if daily else 0
    return total


def calc_score(data, days, metric):
    raw_prices = [d["avg_price"] for d in data]
    prices = _clean_prices(raw_prices)
    total_vol = sum(d["count"] for d in data)
    daily_vol = total_vol / days if days else 0
    med_p = statistics.median(prices)
    price_usd = med_p / 100

    cv = 0
    if med_p and len(prices) > 1:
        cv = statistics.stdev(prices) / statistics.mean(prices)
    stability = 1 / (1 + cv)

    if metric == "trade":
        base = math.log(1 + daily_vol) * math.log(1 + price_usd)
        return round(base * stability * 10, 1)
    # market (default)
    return round(math.log(1 + daily_vol) * stability, 2)


def calc_volatility(data, metric):
    raw_prices = [d["avg_price"] for d in data]
    prices = _clean_prices(raw_prices)
    if len(prices) < 2:
        return 0
    med = statistics.median(prices)
    if not med:
        return 0
    if metric == "range_pct":
        return (max(prices) - min(prices)) / med
    # cv (default)
    return statistics.stdev(prices) / statistics.mean(prices) if statistics.mean(prices) else 0


def parse_order_expression(expression, def_index, paint_index):
    if not expression:
        return "Item"

    expr = expression
    parts = []

    # FloatValue range
    float_min = None
    float_max = None
    for m in re.finditer(r'FloatValue\s*(>=?)\s*([\d.]+)', expr):
        float_min = m.group(2)
    for m in re.finditer(r'FloatValue\s*(<=?)\s*([\d.]+)', expr):
        float_max = m.group(2)

    def trim(v):
        return v.rstrip('0').rstrip('.')

    if float_min and float_max:
        parts.append(f"Float {trim(float_min)}–{trim(float_max)}")
    elif float_max:
        parts.append(f"Float <{trim(float_max)}")
    elif float_min:
        parts.append(f"Float >{trim(float_min)}")

    seeds = re.findall(r'PaintSeed\s*==\s*(\d+)', expr)
    if seeds:
        if len(seeds) <= 3:
            parts.append(f"Seed {', '.join(seeds)}")
        else:
            parts.append(f"Seed {', '.join(seeds[:3])}...")

    m = re.search(r'StatTrak\s*==\s*(true|false)', expr)
    if m:
        parts.append("StatTrak" if m.group(1) == "true" else "No ST")

    m = re.search(r'Souvenir\s*==\s*(true|false)', expr)
    if m:
        parts.append("Souvenir" if m.group(1) == "true" else "No Souv")

    m = re.search(r'Rarity\s*==\s*(\d+)', expr)
    if m:
        r_id = int(m.group(1))
        parts.append(RARITY_NAMES.get(r_id, f"Rarity {r_id}"))

    if "HasSticker" in expr:
        parts.append("Stickers")

    return " + ".join(parts) if parts else "Item"


# ═══════════════════════════════════════════════════════════════════
# Arc circle widget
# ═══════════════════════════════════════════════════════════════════

def _interpolate_color(c1, c2, t):
    """Линейная интерполяция между двумя QColor, t: 0..1."""
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


class SingleArcCircle(QWidget):
    """Круг: арка = ликвидность (gradient), центр = score, price, volatility."""

    def __init__(self, label, score, price_val, volatility, volume, max_volume,
                 score_mode="market", vol_mode="total", volatility_mode="cv",
                 parent=None):
        super().__init__(parent)
        self.period_label = label
        self.score = score
        self.price_val = price_val
        self.volatility = volatility
        self.volume = volume
        self.max_volume = max_volume
        self.score_mode = score_mode
        self.vol_mode = vol_mode
        self.volatility_mode = volatility_mode
        self._hovered = False
        self.setMouseTracking(True)
        self.setFixedSize(80, 80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _fmt_volatility(self):
        if self.volatility_mode == "range_pct":
            return f"\u00b1{self.volatility * 100:.0f}%"
        return f"CV {self.volatility * 100:.0f}%"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        arc_thickness = 5
        radius = min(w, h) / 2 - 6
        max_sweep = 270
        start_angle_deg = 225

        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        # Трек (фон)
        track_color = QColor(Theme.BG_LIGHT) if not self._hovered else QColor(Theme.BG_HOVER)
        painter.setPen(QPen(track_color, arc_thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, int(start_angle_deg * 16), int(-max_sweep * 16))

        # Арка = volume / max_volume
        fill_ratio = min(self.volume / self.max_volume, 1.0) if self.max_volume > 0 else 0
        sweep = max_sweep * fill_ratio

        # Градиентная арка
        if sweep > 0:
            primary = QColor(Theme.PRIMARY)
            start_color = QColor(primary)
            start_color.setAlpha(60)
            end_color = QColor(primary)
            if self._hovered:
                start_color = start_color.lighter(120)
                end_color = end_color.lighter(120)

            thickness = arc_thickness + (1 if self._hovered else 0)
            n_seg = max(int(sweep / 4), 2)
            seg_sweep = sweep / n_seg

            for i in range(n_seg):
                t = i / max(n_seg - 1, 1)
                color = _interpolate_color(start_color, end_color, t)
                angle = start_angle_deg - seg_sweep * i
                painter.setPen(QPen(color, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                painter.drawArc(rect, int(angle * 16), int(-(seg_sweep + 0.5) * 16))

            # Скруглённые концы
            painter.setPen(QPen(start_color, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(rect, int(start_angle_deg * 16), int(-1 * 16))
            painter.setPen(QPen(end_color, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            end_angle = start_angle_deg - sweep
            painter.drawArc(rect, int((end_angle + 1) * 16), int(-1 * 16))

            # Точка на конце
            end_rad = math.radians(start_angle_deg - sweep)
            dot_x = cx + radius * math.cos(end_rad)
            dot_y = cy - radius * math.sin(end_rad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(end_color))
            painter.drawEllipse(QPointF(dot_x, dot_y), 2.5, 2.5)

        # Score (над ценой)
        painter.setPen(QColor(Theme.TEXT_SECONDARY))
        painter.setFont(QFont(Theme.FONT_FAMILY, 8))
        score_text = f"{self.score:.1f}" if self.score >= 10 else f"{self.score:.2f}"
        painter.drawText(QRectF(0, cy - 22, w, 12), Qt.AlignmentFlag.AlignCenter, score_text)

        # Price (центр, крупно, PRIMARY)
        painter.setPen(QColor(Theme.PRIMARY))
        painter.setFont(QFont(Theme.FONT_FAMILY, 11, QFont.Weight.Bold))
        painter.drawText(QRectF(0, cy - 10, w, 18), Qt.AlignmentFlag.AlignCenter, f"${self.price_val:.2f}")

        # Volume (под ценой)
        painter.setPen(QColor(Theme.TEXT_SECONDARY))
        painter.setFont(QFont(Theme.FONT_FAMILY, 8))
        if self.vol_mode in ("avg_day", "med_day"):
            vol_text = f"{self.volume}/d"
        else:
            vol_text = f"{self.volume} sold"
        painter.drawText(QRectF(0, cy + 8, w, 12), Qt.AlignmentFlag.AlignCenter, vol_text)

        # Period label — в центре разрыва арки
        painter.setPen(QColor(Theme.TEXT_SECONDARY))
        painter.setFont(QFont(Theme.FONT_FAMILY, 7, QFont.Weight.Bold))
        painter.drawText(QRectF(0, cy + radius - 12, w, 12), Qt.AlignmentFlag.AlignCenter, self.period_label)

        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        QToolTip.hideText()

    def mouseMoveEvent(self, event):
        if self._hovered:
            vol_str = f"{self.volume}/d" if self.vol_mode in ("avg_day", "med_day") else str(self.volume)
            score_label = "Trade Rating" if self.score_mode == "trade" else "Market Score"
            text = (f"{score_label}: {self.score:.2f}\n"
                    f"Price: ${self.price_val:.2f}\n"
                    f"Volume: {vol_str}\n"
                    f"Volatility: {self._fmt_volatility()}")
            QToolTip.showText(self.mapToGlobal(event.pos()), text, self)


# ═══════════════════════════════════════════════════════════════════
# Price chart with volume bars and tooltip
# ═══════════════════════════════════════════════════════════════════

class PriceChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_data = []
        self.data = []
        self._points = []
        self._hover_idx = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(120)

    def set_data(self, graph_data):
        self._all_data = graph_data or []
        self.set_period(90)

    def set_period(self, days):
        filtered = filter_by_days(self._all_data, days) if days < 999 else self._all_data
        self.data = list(reversed(filtered))
        self._points = []
        self._hover_idx = -1
        self.update()

    def paintEvent(self, event):
        if not self.data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 44, 10, 8, 20

        prices = [d["avg_price"] / 100 for d in self.data]
        volumes = [d.get("count", 0) for d in self.data]
        min_p, max_p = min(prices), max(prices)
        max_vol = max(volumes) if volumes else 1
        rng = max_p - min_p or 0.01

        cw = w - pad_l - pad_r
        ch = h - pad_t - pad_b

        painter.fillRect(self.rect(), QColor(Theme.BG_WHITE))

        painter.setPen(QPen(QColor(Theme.BORDER_GRID), 1))
        for i in range(5):
            y = pad_t + ch * i / 4
            painter.drawLine(int(pad_l), int(y), int(w - pad_r), int(y))

        label_font = QFont(Theme.FONT_FAMILY, 7)
        painter.setFont(label_font)
        painter.setPen(QColor(Theme.TEXT_SECONDARY))

        for i in range(5):
            y = pad_t + ch * i / 4
            price = max_p - rng * i / 4
            painter.drawText(QRect(0, int(y) - 7, pad_l - 4, 14),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"${price:.2f}")

        n = len(self.data)
        if n < 2:
            painter.end()
            return

        step = max(1, n // 4)
        for i in range(0, n, step):
            x = pad_l + cw * i / (n - 1)
            short = self.data[i]["day"][5:10]
            painter.drawText(QRect(int(x) - 20, h - pad_b + 2, 40, 16),
                             Qt.AlignmentFlag.AlignCenter, short)

        chart_bottom = h - pad_b

        vol_max_h = ch * 0.30
        bar_w = max(2, cw / n * 0.6)
        vol_color = QColor(Theme.PRIMARY)
        vol_color.setAlpha(35)
        vol_color_hover = QColor(Theme.PRIMARY)
        vol_color_hover.setAlpha(80)

        for i, d in enumerate(self.data):
            x = pad_l + cw * i / (n - 1)
            vol = d.get("count", 0)
            bar_h = (vol / max_vol) * vol_max_h if max_vol > 0 else 0
            if bar_h < 1:
                bar_h = 1
            color = vol_color_hover if i == self._hover_idx else vol_color
            painter.fillRect(QRectF(x - bar_w / 2, chart_bottom - bar_h, bar_w, bar_h), color)

        self._points = []
        for i, d in enumerate(self.data):
            x = pad_l + cw * i / (n - 1)
            y = pad_t + ch * (1 - (d["avg_price"] / 100 - min_p) / rng)
            self._points.append(QPointF(x, y))

        fill_path = QPainterPath()
        fill_path.moveTo(QPointF(self._points[0].x(), chart_bottom))
        for p in self._points:
            fill_path.lineTo(p)
        fill_path.lineTo(QPointF(self._points[-1].x(), chart_bottom))
        fill_path.closeSubpath()
        fc = QColor(Theme.PRIMARY)
        fc.setAlpha(25)
        painter.fillPath(fill_path, fc)

        painter.setPen(QPen(QColor(Theme.PRIMARY), 2))
        for i in range(len(self._points) - 1):
            painter.drawLine(self._points[i], self._points[i + 1])

        if 0 <= self._hover_idx < len(self._points):
            px = self._points[self._hover_idx]
            line_pen = QPen(QColor(Theme.TEXT_SECONDARY), 1, Qt.PenStyle.DashLine)
            painter.setPen(line_pen)
            painter.drawLine(QPointF(px.x(), pad_t), QPointF(px.x(), chart_bottom))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(Theme.PRIMARY)))
            painter.drawEllipse(px, 4, 4)

        painter.end()

    def mouseMoveEvent(self, event):
        if not self._points:
            return

        mx = event.pos().x()
        best_idx = -1
        best_dist = 999

        for i, p in enumerate(self._points):
            dist = abs(p.x() - mx)
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_dist > 20:
            best_idx = -1

        if best_idx != self._hover_idx:
            self._hover_idx = best_idx
            self.update()

            if 0 <= best_idx < len(self.data):
                d = self.data[best_idx]
                price = cents_to_dollars(d["avg_price"])
                count = d.get("count", 0)
                date = format_date(d["day"])
                text = f"{price}\n{count} Sold\n{date}"
                QToolTip.showText(self.mapToGlobal(event.pos()), text, self)
            else:
                QToolTip.hideText()

    def leaveEvent(self, event):
        if self._hover_idx != -1:
            self._hover_idx = -1
            self.update()
        QToolTip.hideText()


# ═══════════════════════════════════════════════════════════════════
# Sortable numeric item
# ═══════════════════════════════════════════════════════════════════

class NumericItem(QTableWidgetItem):
    def __init__(self, text, sort_value):
        super().__init__(text)
        self._sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)
