# modules/ui_tab1/item_info_dialog.py

import logging
import math
import re
import statistics
from datetime import datetime, timedelta, timezone

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QWidget, QPushButton, QHeaderView,
    QAbstractItemView, QFrame, QLineEdit, QToolTip, QMenu,
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QPainterPath, QBrush, QPixmap
from PyQt6.QtCore import Qt, QRect, QPointF, QTimer, QRectF, QThreadPool, QSettings
from PyQt6.QtGui import QActionGroup

from modules.theme import Theme
from modules.loading_spinner import LoadingOverlay
from modules.workers import ApiWorker
from modules.utils import cache_image_async
from modules.api import (
    get_item_listings, get_item_sales, get_item_buy_orders, get_item_graph,
)

WEAR_FLOAT_RANGES = {
    "Factory New": (0, 0.07),
    "Minimal Wear": (0.07, 0.15),
    "Field-Tested": (0.15, 0.38),
    "Well-Worn": (0.38, 0.45),
    "Battle-Scarred": (0.45, 1),
}

RARITY_NAMES = {
    0: "Consumer", 1: "Industrial", 2: "Mil-Spec",
    3: "Restricted", 4: "Classified", 5: "Covert", 6: "Contraband",
}


def _filter_by_days(graph, days):
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



STATS_SETTINGS_KEYS = {
    "score": "stats_score_metric",
    "price": "stats_price_metric",
    "volume": "stats_volume_metric",
    "volatility": "stats_volatility_metric",
}


def _calc_price(data, metric):
    raw_prices = [d["avg_price"] for d in data]
    prices = _clean_prices(raw_prices)
    if metric == "average":
        return statistics.mean(prices) / 100
    if metric == "min":
        return min(prices) / 100
    if metric == "max":
        return max(prices) / 100
    if metric == "weighted":
        # Weighted использует raw данные, но с IQR-порогом
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



def _calc_volume(data, days, metric):
    total = sum(d["count"] for d in data)
    if metric == "avg_day":
        return round(total / days, 1) if days else 0
    if metric == "med_day":
        daily = [d["count"] for d in data]
        return round(statistics.median(daily), 1) if daily else 0
    return total


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


def _calc_score(data, days, metric):
    raw_prices = [d["avg_price"] for d in data]
    prices = _clean_prices(raw_prices)
    total_vol = sum(d["count"] for d in data)
    daily_vol = total_vol / days if days else 0
    med_p = statistics.median(prices)
    price_usd = med_p / 100

    # CV на очищенных данных
    cv = 0
    if med_p and len(prices) > 1:
        cv = statistics.stdev(prices) / statistics.mean(prices)
    stability = 1 / (1 + cv)

    if metric == "trade":
        base = math.log(1 + daily_vol) * math.log(1 + price_usd)
        return round(base * stability * 10, 1)
    # market (default)
    return round(math.log(1 + daily_vol) * stability, 2)


def _calc_volatility(data, metric):
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


def days_ago(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        d, h = delta.days, delta.seconds // 3600
        return f"{h}h" if d == 0 else f"{d}d"
    except Exception:
        return ""


def cents_to_dollars(cents):
    return f"${cents / 100:.2f}"


def format_date(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return ""


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


class _SingleArcCircle(QWidget):
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

        # Score (центр, крупно)
        painter.setPen(QColor(Theme.PRIMARY))
        painter.setFont(QFont(Theme.FONT_FAMILY, 10, QFont.Weight.Bold))
        score_text = f"{self.score:.1f}" if self.score >= 10 else f"{self.score:.2f}"
        painter.drawText(QRectF(0, cy - 20, w, 16), Qt.AlignmentFlag.AlignCenter, score_text)

        # Price (под score)
        painter.setPen(QColor(Theme.TEXT_SECONDARY))
        painter.setFont(QFont(Theme.FONT_FAMILY, 8))
        painter.drawText(QRectF(0, cy - 5, w, 12), Qt.AlignmentFlag.AlignCenter, f"${self.price_val:.2f}")

        # Volatility (под price)
        painter.setPen(QColor(Theme.TEXT_SECONDARY))
        painter.setFont(QFont(Theme.FONT_FAMILY, 7))
        painter.drawText(QRectF(0, cy + 7, w, 10), Qt.AlignmentFlag.AlignCenter, self._fmt_volatility())

        # Period label — в центре разрыва арки (270° = самый низ)
        painter.setPen(QColor(Theme.TEXT_SECONDARY))
        painter.setFont(QFont(Theme.FONT_FAMILY, 7, QFont.Weight.Bold))
        painter.drawText(QRectF(0, cy + radius - 8, w, 12), Qt.AlignmentFlag.AlignCenter, self.period_label)

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
            text = (f"{self.period_label}\n"
                    f"{score_label}: {self.score:.2f}\n"
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
        filtered = _filter_by_days(self._all_data, days) if days < 999 else self._all_data
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


# ═══════════════════════════════════════════════════════════════════
# Main Dialog
# ═══════════════════════════════════════════════════════════════════

class ItemInfoDialog(QDialog):
    def __init__(self, market_hash_name, def_index, paint_index,
                 sticker_index="", inspect_link="", wear_name="",
                 api_key="", icon_url="", parent=None):
        super().__init__(parent)

        self.item_name = market_hash_name
        self.icon_url = icon_url
        self.def_index = def_index
        self.paint_index = paint_index
        self.sticker_index = sticker_index
        self.inspect_link = inspect_link
        self.wear_name = wear_name
        self.api_key = api_key

        self.is_stattrak = "StatTrak\u2122" in market_hash_name
        self.is_souvenir = "Souvenir" in market_hash_name

        # Определяем category для API
        if self.is_stattrak:
            self.category = 2
        elif self.is_souvenir:
            self.category = 3
        else:
            self.category = 1

        # Float range по wear condition
        self.wear_min, self.wear_max = WEAR_FLOAT_RANGES.get(wear_name, (None, None))

        # Кэш данных и сохранённые значения фильтров
        self._cached_listings = None
        self._saved_float_min = ''
        self._saved_float_max = ''
        self._listings_data = []
        self._sales_data = []
        self._orders_data = []
        self._graph_data = []
        self._pending_requests = 0

        # Настройки статистики
        _s = QSettings("MyCompany", "SteamInventoryApp")
        self._stats_config = {
            "score": _s.value("stats_score_metric", "market", type=str),
            "price": _s.value("stats_price_metric", "median", type=str),
            "volume": _s.value("stats_volume_metric", "total", type=str),
            "volatility": _s.value("stats_volatility_metric", "cv", type=str),
        }

        self.setWindowTitle(self.item_name)
        self.resize(636, 680)
        self.setMinimumSize(600, 550)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BG_WHITE}; }}
            QLabel {{ color: {Theme.TEXT_PRIMARY}; }}
        """)

        self._build_ui()
        self._build_settings_btn()
        Theme.apply_titlebar_theme(self)

        self._loading = LoadingOverlay(self, "Loading item data...")
        QTimer.singleShot(50, self._start_loading)

    def _build_settings_btn(self):
        self._stats_btn = QPushButton("\u2699", self)
        self._stats_btn.setFixedSize(22, 22)
        self._stats_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stats_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {Theme.TEXT_SECONDARY}; font-size: 13pt;
            }}
            QPushButton:hover {{ color: {Theme.PRIMARY}; }}
        """)
        self._stats_btn.clicked.connect(self._show_stats_menu)
        self._position_settings_btn()

    def _position_settings_btn(self):
        self._stats_btn.move(self.width() - 30, 6)

    def _on_icon_loaded(self, path):
        import os
        if not path or not os.path.exists(path):
            return
        pm = QPixmap(path).scaled(
            64, 48,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not pm.isNull():
            self._item_image.setPixmap(pm)

    def _start_loading(self):
        self._loading.start("Loading item data...")
        self._fetch_all_data()

    def _fetch_all_data(self):
        """Запускаем 4 параллельных запроса."""
        self._pending_requests = 4
        pool = QThreadPool.globalInstance()

        # 1. Listings
        w1 = ApiWorker(
            get_item_listings, self.api_key, self.def_index,
            self.paint_index, self.sticker_index,
            self.category, self.wear_min, self.wear_max,
        )
        w1.signals.result.connect(self._on_listings_loaded)
        w1.signals.error.connect(self._on_request_error)
        pool.start(w1)

        # 2. Sales
        w2 = ApiWorker(get_item_sales, self.api_key, self.item_name)
        w2.signals.result.connect(self._on_sales_loaded)
        w2.signals.error.connect(self._on_request_error)
        pool.start(w2)

        # 3. Buy Orders
        # Скины (paint_index) → GET /buy-orders/item по inspect_link
        # Стикеры, кейсы и тд → POST /buy-orders/similar-orders
        if self.paint_index and self.inspect_link:
            w3 = ApiWorker(
                get_item_buy_orders, self.api_key,
                inspect_link=self.inspect_link, limit=5,
            )
        else:
            w3 = ApiWorker(
                get_item_buy_orders, self.api_key,
                market_hash_name=self.item_name, limit=10,
            )
        w3.signals.result.connect(self._on_orders_loaded)
        w3.signals.error.connect(self._on_request_error)
        pool.start(w3)

        # 4. Graph
        w4 = ApiWorker(get_item_graph, self.api_key, self.item_name)
        w4.signals.result.connect(self._on_graph_loaded)
        w4.signals.error.connect(self._on_request_error)
        pool.start(w4)

    def _on_request_done(self):
        self._pending_requests -= 1
        if self._pending_requests <= 0:
            self._loading.stop()

    def _on_request_error(self, error):
        e, tb = error
        logging.error(f"Item info request error: {e}")
        self._on_request_done()

    def _on_listings_loaded(self, data):
        if data:
            listings = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(listings, list):
                self._listings_data = listings
                self._cached_listings = listings
                self._populate_listings_table(listings)
        self._on_request_done()

    def _on_sales_loaded(self, data):
        if data:
            sales = data if isinstance(data, list) else []
            self._sales_data = sales
            self._populate_sales_table(sales)
        self._on_request_done()

    def _on_orders_loaded(self, data):
        if data:
            orders = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(orders, list):
                orders = []
            self._orders_data = orders
            self._populate_orders_table(orders)
        self._on_request_done()

    def _on_graph_loaded(self, data):
        if data:
            graph = data if isinstance(data, list) else []
            self._graph_data = graph
            self._chart.set_data(graph)
            self._rebuild_stats(graph)
        self._on_request_done()

    # ══════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        root.addLayout(self._build_top_row())

        panel_w = 300

        mid = QHBoxLayout()
        mid.setSpacing(6)
        listings_panel = self._build_listings_panel()
        listings_panel.setFixedWidth(panel_w)
        mid.addWidget(listings_panel)
        sales_panel = self._build_sales_panel()
        sales_panel.setFixedWidth(panel_w)
        mid.addWidget(sales_panel)
        root.addLayout(mid, stretch=1)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        orders_panel = self._build_orders_panel()
        orders_panel.setFixedWidth(panel_w)
        bottom.addWidget(orders_panel)
        chart_panel = self._build_chart_panel()
        chart_panel.setFixedWidth(panel_w)
        bottom.addWidget(chart_panel)
        root.addLayout(bottom)

    # ══════════════════════════════════════════════════════════
    # TOP ROW: filters + stats placeholder
    # ══════════════════════════════════════════════════════════

    def _build_top_row(self):
        outer = QHBoxLayout()
        outer.setSpacing(8)
        outer.setContentsMargins(0, 0, 0, 0)

        # Иконка предмета
        self._item_image = QLabel()
        self._item_image.setFixedSize(64, 48)
        self._item_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._item_image.setStyleSheet("border: none;")
        outer.addWidget(self._item_image)

        if self.icon_url:
            cache_image_async(self.icon_url, self._on_icon_loaded)

        input_h = 24
        label_w = 58

        filters_col = QVBoxLayout()
        filters_col.setSpacing(2)
        filters_col.setContentsMargins(0, 0, 0, 0)

        # Ряд 1: Float Min Max
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        row1.setContentsMargins(0, 0, 0, 0)

        self._float_label = QPushButton("Float")
        self._float_label.setFixedSize(label_w, input_h)
        self._float_label.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_SMALL))
        self._float_label.setCursor(Qt.CursorShape.ArrowCursor)
        self._update_clear_label(False)
        self._float_label.clicked.connect(self._clear_all_filters)
        row1.addWidget(self._float_label)

        self._float_min = QLineEdit()
        self._float_min.setPlaceholderText("Min")
        self._float_min.setFixedSize(65, input_h)
        self._float_min.setStyleSheet(Theme.input_style())
        self._float_min.returnPressed.connect(self._apply_filters)
        self._float_min.textChanged.connect(self._check_filters_active)
        row1.addWidget(self._float_min)

        self._float_max = QLineEdit()
        self._float_max.setPlaceholderText("Max")
        self._float_max.setFixedSize(65, input_h)
        self._float_max.setStyleSheet(Theme.input_style())
        self._float_max.returnPressed.connect(self._apply_filters)
        self._float_max.textChanged.connect(self._check_filters_active)
        row1.addWidget(self._float_max)
        filters_col.addLayout(row1)

        # Ряд 2: переключаемый фильтр
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        row2.setContentsMargins(0, 0, 0, 0)
        self._build_switchable_filter(row2, input_h, label_w)
        filters_col.addLayout(row2)

        outer.addLayout(filters_col)

        # Stats placeholder — заполнится после загрузки graph
        self._stats_container = QWidget()
        self._stats_container.setFixedSize(260, 80)
        self._stats_layout = QHBoxLayout(self._stats_container)
        self._stats_layout.setContentsMargins(0, 0, 0, 0)
        self._stats_layout.setSpacing(0)
        outer.addWidget(self._stats_container, alignment=Qt.AlignmentFlag.AlignVCenter)

        return outer

    def _show_stats_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(Theme.menu_style())

        score_menu = menu.addMenu("Score")
        score_group = QActionGroup(score_menu)
        for key, label in [("market", "Market Score"), ("trade", "Trade Rating")]:
            action = score_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self._stats_config["score"] == key)
            action.triggered.connect(lambda _, k=key: self._set_stats("score", k))
            score_group.addAction(action)

        price_menu = menu.addMenu("Price")
        price_group = QActionGroup(price_menu)
        for key, label in [("median", "Median"), ("average", "Average"),
                           ("weighted", "Weighted"), ("min", "Min"), ("max", "Max")]:
            action = price_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self._stats_config["price"] == key)
            action.triggered.connect(lambda _, k=key: self._set_stats("price", k))
            price_group.addAction(action)

        vol_menu = menu.addMenu("Volume")
        vol_group = QActionGroup(vol_menu)
        for key, label in [("total", "Total"), ("avg_day", "Avg/day"),
                           ("med_day", "Med/day")]:
            action = vol_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self._stats_config["volume"] == key)
            action.triggered.connect(lambda _, k=key: self._set_stats("volume", k))
            vol_group.addAction(action)

        volat_menu = menu.addMenu("Volatility")
        volat_group = QActionGroup(volat_menu)
        for key, label in [("cv", "CV (std/mean)"), ("range_pct", "Range (max-min)/med")]:
            action = volat_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self._stats_config["volatility"] == key)
            action.triggered.connect(lambda _, k=key: self._set_stats("volatility", k))
            volat_group.addAction(action)

        menu.exec(self._stats_btn.mapToGlobal(self._stats_btn.rect().bottomLeft()))

    def _set_stats(self, category, value):
        self._stats_config[category] = value
        QSettings("MyCompany", "SteamInventoryApp").setValue(
            STATS_SETTINGS_KEYS[category], value
        )
        self._rebuild_stats(self._graph_data)

    def _rebuild_stats(self, graph):
        while self._stats_layout.count():
            child = self._stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not graph:
            return

        cfg = self._stats_config

        periods = [("7d", 7), ("30d", 30), ("90d", 90)]
        period_data = []
        for label, days in periods:
            data = _filter_by_days(graph, days)
            if not data:
                continue
            vol = _calc_volume(data, days, cfg["volume"])
            period_data.append((label, days, data, vol))

        max_vol = max((v for _, _, _, v in period_data), default=1) or 1

        for label, days, data, vol in period_data:
            price = _calc_price(data, cfg["price"])
            score = _calc_score(data, days, cfg["score"])
            volatility = _calc_volatility(data, cfg["volatility"])

            circle = _SingleArcCircle(
                label, score, price, volatility, vol, max_vol,
                score_mode=cfg["score"],
                vol_mode=cfg["volume"],
                volatility_mode=cfg["volatility"],
            )
            self._stats_layout.addWidget(circle, alignment=Qt.AlignmentFlag.AlignCenter)

    def _build_switchable_filter(self, lay, input_h, label_w=58):
        self._filter_types = [
            {"name": "Pattern", "placeholder": "e.g. 323, 715", "mode": "single"},
            {"name": "Fade %", "placeholder_min": "Min %", "placeholder_max": "Max %", "mode": "range"},
            {"name": "Blue %", "placeholder_min": "Min %", "placeholder_max": "Max %", "mode": "range"},
            {"name": "Keychain", "placeholder_min": "Min", "placeholder_max": "Max", "mode": "range"},
        ]
        self._current_filter_idx = 0
        self._filter_values = {}

        self._filter_label = QPushButton("Pattern \u25be")
        self._filter_label.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_SMALL))
        self._filter_label.setFixedSize(label_w, input_h)
        self._filter_label.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.PRIMARY};
                border: none;
                padding: 0 4px;
                text-align: left;
            }}
            QPushButton:hover {{
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        self._filter_label.setCursor(Qt.CursorShape.PointingHandCursor)

        self._filter_selector = QMenu(self)
        self._filter_selector.setStyleSheet(Theme.menu_style())
        for i, ft in enumerate(self._filter_types):
            action = self._filter_selector.addAction(ft["name"])
            action.triggered.connect(lambda checked, idx=i: self._switch_filter(idx))

        self._filter_label.clicked.connect(
            lambda: self._filter_selector.exec(
                self._filter_label.mapToGlobal(self._filter_label.rect().bottomLeft())
            )
        )
        lay.addWidget(self._filter_label)

        self._filter_input_single = QLineEdit()
        self._filter_input_single.setPlaceholderText("e.g. 323, 715")
        self._filter_input_single.setFixedSize(134, input_h)
        self._filter_input_single.setStyleSheet(Theme.input_style())
        self._filter_input_single.returnPressed.connect(self._apply_filters)
        self._filter_input_single.textChanged.connect(self._check_filters_active)
        lay.addWidget(self._filter_input_single)

        self._filter_input_min = QLineEdit()
        self._filter_input_min.setPlaceholderText("Min")
        self._filter_input_min.setFixedSize(65, input_h)
        self._filter_input_min.setStyleSheet(Theme.input_style())
        self._filter_input_min.returnPressed.connect(self._apply_filters)
        self._filter_input_min.textChanged.connect(self._check_filters_active)
        self._filter_input_min.hide()
        lay.addWidget(self._filter_input_min)

        self._filter_input_max = QLineEdit()
        self._filter_input_max.setPlaceholderText("Max")
        self._filter_input_max.setFixedSize(65, input_h)
        self._filter_input_max.setStyleSheet(Theme.input_style())
        self._filter_input_max.returnPressed.connect(self._apply_filters)
        self._filter_input_max.textChanged.connect(self._check_filters_active)
        self._filter_input_max.hide()
        lay.addWidget(self._filter_input_max)

    def _switch_filter(self, idx):
        cur = self._filter_types[self._current_filter_idx]
        if cur["mode"] == "single":
            self._filter_values[cur["name"]] = self._filter_input_single.text()
        else:
            self._filter_values[f"{cur['name']}_min"] = self._filter_input_min.text()
            self._filter_values[f"{cur['name']}_max"] = self._filter_input_max.text()

        self._current_filter_idx = idx
        ft = self._filter_types[idx]
        self._filter_label.setText(f"{ft['name']} \u25be")

        if ft["mode"] == "single":
            self._filter_input_single.show()
            self._filter_input_min.hide()
            self._filter_input_max.hide()
            self._filter_input_single.setPlaceholderText(ft["placeholder"])
            self._filter_input_single.setText(self._filter_values.get(ft["name"], ""))
            self._filter_input_single.setFocus()
        else:
            self._filter_input_single.hide()
            self._filter_input_min.show()
            self._filter_input_max.show()
            self._filter_input_min.setPlaceholderText(ft["placeholder_min"])
            self._filter_input_max.setPlaceholderText(ft["placeholder_max"])
            self._filter_input_min.setText(self._filter_values.get(f"{ft['name']}_min", ""))
            self._filter_input_max.setText(self._filter_values.get(f"{ft['name']}_max", ""))
            self._filter_input_min.setFocus()

    # ══════════════════════════════════════════════════════════
    # FILTERS LOGIC
    # ══════════════════════════════════════════════════════════

    def _parse_float(self, text):
        try:
            return float(text.strip()) if text.strip() else None
        except ValueError:
            return None

    def _apply_filters(self):
        fmin = self._parse_float(self._float_min.text())
        fmax = self._parse_float(self._float_max.text())

        cur = self._filter_types[self._current_filter_idx]
        if cur["mode"] == "single":
            self._filter_values[cur["name"]] = self._filter_input_single.text()
        else:
            self._filter_values[f"{cur['name']}_min"] = self._filter_input_min.text()
            self._filter_values[f"{cur['name']}_max"] = self._filter_input_max.text()

        # Если указан float диапазон — новый API запрос
        has_float_filter = fmin is not None or fmax is not None
        if has_float_filter and self.paint_index:
            # Сохраняем значения ДО async запроса
            self._saved_float_min = self._float_min.text()
            self._saved_float_max = self._float_max.text()
            self._fetch_filtered_listings(fmin, fmax)
            return

        # Если нет float фильтра — восстанавливаем из кэша
        if not has_float_filter and self._cached_listings is not None:
            self._listings_data = self._cached_listings
            self._populate_listings_table(self._cached_listings)

        # Pattern — локальная фильтрация
        patterns = set()
        pat_text = self._filter_values.get("Pattern", "").strip()
        if pat_text:
            for p in pat_text.replace(" ", "").split(","):
                if p.isdigit():
                    patterns.add(int(p))

        for row in range(self.listings_table.rowCount()):
            seed_item = self.listings_table.item(row, 1)
            seed = seed_item._sort_value if isinstance(seed_item, NumericItem) else 0
            hide = bool(patterns and seed not in patterns)
            self.listings_table.setRowHidden(row, hide)

    def _fetch_filtered_listings(self, fmin, fmax):
        """Новый API запрос с пользовательским float диапазоном."""
        pool = QThreadPool.globalInstance()
        w = ApiWorker(
            get_item_listings, self.api_key, self.def_index,
            self.paint_index, self.sticker_index, self.category,
            fmin or self.wear_min, fmax or self.wear_max,
        )
        w.signals.result.connect(self._on_filtered_listings_loaded)
        w.signals.error.connect(self._on_request_error)
        pool.start(w)

    def _on_filtered_listings_loaded(self, data):
        if data:
            listings = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(listings, list):
                self._listings_data = listings
                self._populate_listings_table(listings)

        # Восстанавливаем значения из сохранённых в _apply_filters
        fmin_text = getattr(self, '_saved_float_min', '')
        fmax_text = getattr(self, '_saved_float_max', '')
        if fmin_text or fmax_text:
            self._float_min.setText(fmin_text)
            self._float_max.setText(fmax_text)
            self._update_clear_label(True)

    def _update_clear_label(self, active):
        if active:
            self._float_label.setText("\u2715 Float")
            self._float_label.setCursor(Qt.CursorShape.PointingHandCursor)
            self._float_label.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: #E85454; text-align: left; padding: 0 4px;
                }}
                QPushButton:hover {{ color: {Theme.PRIMARY}; }}
            """)
        else:
            self._float_label.setText("Float")
            self._float_label.setCursor(Qt.CursorShape.ArrowCursor)
            self._float_label.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: {Theme.TEXT_SECONDARY}; text-align: left; padding: 0 4px;
                }}
            """)

    def _check_filters_active(self):
        cur = self._filter_types[self._current_filter_idx]
        if cur["mode"] == "single":
            self._filter_values[cur["name"]] = self._filter_input_single.text()
        else:
            self._filter_values[f"{cur['name']}_min"] = self._filter_input_min.text()
            self._filter_values[f"{cur['name']}_max"] = self._filter_input_max.text()

        active = bool(
            self._float_min.text() or self._float_max.text()
            or any(v for v in self._filter_values.values())
        )
        self._update_clear_label(active)

    def _clear_all_filters(self):
        self._float_min.clear()
        self._float_max.clear()
        self._filter_input_single.clear()
        self._filter_input_min.clear()
        self._filter_input_max.clear()
        self._filter_values.clear()
        self._update_clear_label(False)
        self._apply_filters()

    # ══════════════════════════════════════════════════════════
    # LISTINGS TABLE
    # ══════════════════════════════════════════════════════════

    def _build_listings_panel(self):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_WHITE};
                border: 1px solid {Theme.BORDER_GRID};
                border-radius: {Theme.RADIUS}px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)

        title = QLabel("Current Listings")
        title.setFont(QFont(Theme.FONT_FAMILY, 9))
        title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        cols = ["Float", "Seed", "Price", "Days"]
        self.listings_table = QTableWidget(0, len(cols))
        self.listings_table.setHorizontalHeaderLabels(cols)
        self.listings_table.setStyleSheet(Theme.table_style())
        self.listings_table.horizontalHeader().setStyleSheet(Theme.table_header_style())
        self.listings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.listings_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.listings_table.verticalHeader().setDefaultSectionSize(28)
        self.listings_table.verticalHeader().setVisible(False)
        self.listings_table.setAlternatingRowColors(True)
        self.listings_table.setSortingEnabled(True)

        h = self.listings_table.horizontalHeader()
        h.setStretchLastSection(False)
        # panel=300 - border(2) - margins(6) - table_border(2) - scrollbar(17) = 273
        for col, w in enumerate([128, 46, 55, 49]):
            self.listings_table.setColumnWidth(col, w)
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)

        lay.addWidget(self.listings_table)
        return frame

    def _populate_listings_table(self, listings):
        self.listings_table.setSortingEnabled(False)
        self.listings_table.setRowCount(0)

        for entry in listings:
            row = self.listings_table.rowCount()
            self.listings_table.insertRow(row)

            item = entry.get("item", {})
            fv = item.get("float_value", 0)
            seed = item.get("paint_seed", 0)
            price = entry.get("price", 0)
            created = entry.get("created_at", "")

            float_item = NumericItem(f"{fv:.14f}", fv)
            float_item.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_SMALL))
            self.listings_table.setItem(row, 0, float_item)

            seed_item = NumericItem(str(seed), seed)
            self.listings_table.setItem(row, 1, seed_item)

            price_item = NumericItem(cents_to_dollars(price), price)
            price_item.setForeground(QColor(Theme.PRIMARY))
            price_item.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE, QFont.Weight.Bold))
            self.listings_table.setItem(row, 2, price_item)

            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                days_val = (datetime.now(timezone.utc) - dt).total_seconds()
            except Exception:
                days_val = 0
            days_item = NumericItem(days_ago(created), days_val)
            self.listings_table.setItem(row, 3, days_item)

        self.listings_table.setSortingEnabled(True)
        self.listings_table.sortItems(2, Qt.SortOrder.AscendingOrder)

    # ══════════════════════════════════════════════════════════
    # RECENT SALES
    # ══════════════════════════════════════════════════════════

    def _build_sales_panel(self):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_WHITE};
                border: 1px solid {Theme.BORDER_GRID};
                border-radius: {Theme.RADIUS}px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)

        title = QLabel("Recent Sales")
        title.setFont(QFont(Theme.FONT_FAMILY, 9))
        title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        self._sales_table = QTableWidget(0, 4)
        self._sales_table.setHorizontalHeaderLabels(["Price", "Float", "Seed", "Ago"])
        self._sales_table.setStyleSheet(Theme.table_style())
        self._sales_table.horizontalHeader().setStyleSheet(Theme.table_header_style())
        self._sales_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._sales_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._sales_table.verticalHeader().setDefaultSectionSize(28)
        self._sales_table.verticalHeader().setVisible(False)
        self._sales_table.setAlternatingRowColors(True)

        h = self._sales_table.horizontalHeader()
        h.setStretchLastSection(False)
        for col, w in enumerate([50, 133, 48, 47]):
            self._sales_table.setColumnWidth(col, w)
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)

        lay.addWidget(self._sales_table)
        return frame

    def _populate_sales_table(self, sales):
        tbl = self._sales_table
        tbl.setRowCount(0)

        for sale in sales[:40]:
            r = tbl.rowCount()
            tbl.insertRow(r)

            price = sale.get("price", 0)
            item = sale.get("item", {})
            fv = item.get("float_value", 0)
            seed = item.get("paint_seed", 0)
            sold = sale.get("sold_at", "")

            p = QTableWidgetItem(cents_to_dollars(price))
            p.setForeground(QColor(Theme.PRIMARY))
            p.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE, QFont.Weight.Bold))
            tbl.setItem(r, 0, p)

            f = QTableWidgetItem(f"{fv:.12f}")
            f.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_SMALL))
            tbl.setItem(r, 1, f)

            s = QTableWidgetItem(str(seed))
            tbl.setItem(r, 2, s)

            tbl.setItem(r, 3, QTableWidgetItem(days_ago(sold)))

    # ══════════════════════════════════════════════════════════
    # BUY ORDERS
    # ══════════════════════════════════════════════════════════

    def _build_orders_panel(self):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_WHITE};
                border: 1px solid {Theme.BORDER_GRID};
                border-radius: {Theme.RADIUS}px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)

        title = QLabel("Buy Orders")
        title.setFont(QFont(Theme.FONT_FAMILY, 9))
        title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        self._orders_table = QTableWidget(0, 3)
        self._orders_table.setHorizontalHeaderLabels(["Price", "Qty", "Filter"])
        self._orders_table.setStyleSheet(Theme.table_style())
        self._orders_table.horizontalHeader().setStyleSheet(Theme.table_header_style())
        self._orders_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._orders_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._orders_table.verticalHeader().setDefaultSectionSize(24)
        self._orders_table.verticalHeader().setVisible(False)
        self._orders_table.setAlternatingRowColors(True)
        self._orders_table.setMaximumHeight(160)

        h = self._orders_table.horizontalHeader()
        h.setStretchLastSection(False)
        for col, w in enumerate([55, 35, 188]):
            self._orders_table.setColumnWidth(col, w)
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)

        lay.addWidget(self._orders_table)
        return frame

    def _populate_orders_table(self, orders):
        tbl = self._orders_table
        tbl.setRowCount(0)

        for order in sorted(orders, key=lambda o: o.get("price", 0), reverse=True):
            r = tbl.rowCount()
            tbl.insertRow(r)

            price = order.get("price", 0)
            qty = order.get("qty", 0)
            expression = order.get("expression", "")
            if expression:
                filter_text = parse_order_expression(expression, self.def_index, self.paint_index)
            else:
                filter_text = "Item"

            p = QTableWidgetItem(cents_to_dollars(price))
            p.setForeground(QColor("#4CAF50"))
            p.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_SMALL, QFont.Weight.Bold))
            tbl.setItem(r, 0, p)

            q = QTableWidgetItem(str(qty))
            q.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tbl.setItem(r, 1, q)

            e = QTableWidgetItem(filter_text)
            e.setFont(QFont(Theme.FONT_FAMILY, 10))
            e.setForeground(QColor(Theme.TEXT_SECONDARY))
            tbl.setItem(r, 2, e)

    # ══════════════════════════════════════════════════════════
    # PRICE HISTORY CHART
    # ══════════════════════════════════════════════════════════

    def _build_chart_panel(self):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_WHITE};
                border: 1px solid {Theme.BORDER_GRID};
                border-radius: {Theme.RADIUS}px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(3)

        title = QLabel("Price History")
        title.setFont(QFont(Theme.FONT_FAMILY, 9))
        title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        self._chart = PriceChart()
        lay.addWidget(self._chart, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        btn_row.addStretch()

        self._period_buttons = []
        for label, days in [("30d", 30), ("90d", 90), ("180d", 180), ("All", 999)]:
            btn = QPushButton(label)
            btn.setFixedSize(38, 20)
            btn.setFont(QFont(Theme.FONT_FAMILY, 8))
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.BG_LIGHT};
                    color: {Theme.TEXT_SECONDARY};
                    border: 1px solid {Theme.BORDER_GRID};
                    border-radius: 3px;
                }}
                QPushButton:checked {{
                    background-color: {Theme.PRIMARY};
                    color: {Theme.TEXT_WHITE};
                    border: 1px solid {Theme.PRIMARY};
                }}
                QPushButton:hover:!checked {{
                    background-color: {Theme.HOVER_GRAY};
                }}
            """)
            btn.clicked.connect(lambda checked, d=days, b=btn: self._set_chart_period(d, b))
            btn_row.addWidget(btn)
            self._period_buttons.append(btn)

        self._period_buttons[1].setChecked(True)

        btn_row.addStretch()
        lay.addLayout(btn_row)

        return frame

    def _set_chart_period(self, days, active_btn):
        for btn in self._period_buttons:
            btn.setChecked(btn is active_btn)
        self._chart.set_period(days)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.setGeometry(self.rect())
        if hasattr(self, '_stats_btn'):
            self._position_settings_btn()
