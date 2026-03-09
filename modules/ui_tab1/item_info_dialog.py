# modules/ui_tab1/item_info_dialog.py

import logging
import os
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QWidget, QPushButton, QHeaderView,
    QAbstractItemView, QFrame, QLineEdit, QMenu,
)
from PyQt6.QtGui import QFont, QColor, QPixmap
from PyQt6.QtCore import Qt, QTimer, QThreadPool, QSettings, pyqtSignal
from PyQt6.QtGui import QActionGroup

from modules.theme import Theme
from modules.loading_spinner import LoadingOverlay
from modules.workers import ApiWorker
from modules.utils import cache_image_async, days_ago, cents_to_dollars
from modules.api import (
    get_item_listings, get_item_sales, get_item_buy_orders, get_item_graph,
)
from modules.ui_tab1.constants import WEAR_FLOAT_RANGES
from modules.ui_tab1.item_info_widgets import (
    STATS_SETTINGS_KEYS, NumericItem, SingleArcCircle, PriceChart,
    filter_by_days, calc_price, calc_volume, calc_score, calc_volatility,
    parse_order_expression,
)


class ItemInfoDialog(QDialog):
    price_selected = pyqtSignal(int)
    def __init__(self, market_hash_name, def_index, paint_index,
                 sticker_index="", inspect_link="", wear_name="",
                 api_key="", icon_url="", keychain_index="", parent=None):
        super().__init__(parent)

        self.item_name = market_hash_name
        self.icon_url = icon_url
        self.def_index = def_index
        self.paint_index = paint_index
        self.sticker_index = sticker_index
        self.inspect_link = inspect_link
        self.wear_name = wear_name
        self.api_key = api_key
        self.keychain_index = keychain_index
        self.is_charm = bool(keychain_index)
        self.has_params = bool(paint_index or keychain_index)

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

        self._listings_data = []
        self._sales_data = []
        self._orders_data = []
        self._graph_data = []
        self._pending_requests = 0
        self._current_cursor = None
        self._is_loading_more = False

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
            keychain_index=self.keychain_index,
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
            if isinstance(data, dict):
                self._current_cursor = data.get("cursor")
                listings = data.get("data", [])
            else:
                listings = data if isinstance(data, list) else []
                self._current_cursor = None
            if isinstance(listings, list):
                self._listings_data = listings
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

        self.listings_table.cellDoubleClicked.connect(self._on_listing_double_click)
        self._sales_table.cellDoubleClicked.connect(self._on_sale_double_click)

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

        if self.has_params:
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
            self._float_label.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE))
            self._float_label.setCursor(Qt.CursorShape.ArrowCursor)
            self._set_label_clear_style(self._float_label, "Float", False)
            self._float_label.clicked.connect(self._clear_float_filter)
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

            # Для брелков: скрыть Float, зафиксировать Keychain
            if self.is_charm:
                self._float_label.hide()
                self._float_min.hide()
                self._float_max.hide()
                self._switch_filter(3)
                self._filter_label.setText("Keychain")
                self._filter_label.setCursor(Qt.CursorShape.ArrowCursor)
                try:
                    self._filter_label.clicked.disconnect()
                except TypeError:
                    pass
                self._filter_label.clicked.connect(self._on_charm_label_click)

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
            data = filter_by_days(graph, days)
            if not data:
                continue
            vol = calc_volume(data, days, cfg["volume"])
            period_data.append((label, days, data, vol))

        max_vol = max((v for _, _, _, v in period_data), default=1) or 1

        for label, days, data, vol in period_data:
            price = calc_price(data, cfg["price"])
            score = calc_score(data, days, cfg["score"])
            volatility = calc_volatility(data, cfg["volatility"])

            circle = SingleArcCircle(
                label, score, price, volatility, vol, max_vol,
                score_mode=cfg["score"],
                vol_mode=cfg["volume"],
                volatility_mode=cfg["volatility"],
            )
            self._stats_layout.addWidget(circle, alignment=Qt.AlignmentFlag.AlignCenter)

    def _build_switchable_filter(self, lay, input_h, label_w=58):
        self._filter_types = [
            {"name": "Seed", "placeholder": "e.g. 323, 715", "mode": "single"},
            {"name": "Fade %", "placeholder_min": "Min %", "placeholder_max": "Max %", "mode": "range"},
            {"name": "Blue %", "placeholder_min": "Min %", "placeholder_max": "Max %", "mode": "range"},
            {"name": "Keychain", "placeholder_min": "Min", "placeholder_max": "Max", "mode": "range"},
        ]
        self._current_filter_idx = 0
        self._filter_values = {}

        self._filter_label = QPushButton("Seed \u25be")
        self._filter_label.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE))
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

        self._filter_label.clicked.connect(self._on_filter_label_click)
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

        if not self.is_charm:
            # Заголовок колонки Seed → Fade%/Blue% при соответствующем фильтре
            seed_header = ft["name"] if ft["name"] in ("Fade %", "Blue %") else "Seed"
            self.listings_table.setHorizontalHeaderItem(
                1, QTableWidgetItem(seed_header))
            self._sales_table.setHorizontalHeaderItem(
                2, QTableWidgetItem(seed_header))

            # Перезаполняем таблицы (seed ↔ percentage)
            if self._listings_data:
                self._populate_listings_table(self._listings_data)
            if self._sales_data:
                self._populate_sales_table(self._sales_data)

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
            if not text:
                return None
            return float(text.strip()) if text.strip() else None
        except ValueError:
            return None

    def _collect_filter_params(self):
        """Собирает все активные фильтры в dict для API запроса."""
        params = {}

        fmin = self._parse_float(self._float_min.text())
        fmax = self._parse_float(self._float_max.text())
        if fmin is not None:
            params["min_float"] = fmin
        if fmax is not None:
            params["max_float"] = fmax

        active = self._get_active_filter_name()
        if active == "Seed":
            seeds = self._filter_values.get("Seed", "").strip()
            if seeds:
                params["paint_seed"] = seeds
        elif active == "Fade %":
            v = self._parse_float(self._filter_values.get("Fade %_min"))
            if v is not None:
                params["min_fade"] = v
            v = self._parse_float(self._filter_values.get("Fade %_max"))
            if v is not None:
                params["max_fade"] = v
        elif active == "Blue %":
            v = self._parse_float(self._filter_values.get("Blue %_min"))
            if v is not None:
                params["min_blue"] = v
            v = self._parse_float(self._filter_values.get("Blue %_max"))
            if v is not None:
                params["max_blue"] = v
        elif active == "Keychain":
            v = self._parse_float(self._filter_values.get("Keychain_min"))
            if v is not None:
                params["min_keychain_pattern"] = int(v)
            v = self._parse_float(self._filter_values.get("Keychain_max"))
            if v is not None:
                params["max_keychain_pattern"] = int(v)

        return params

    def _apply_filters(self):
        """Все фильтры отправляют API запрос."""
        cur = self._filter_types[self._current_filter_idx]
        if cur["mode"] == "single":
            self._filter_values[cur["name"]] = self._filter_input_single.text()
        else:
            self._filter_values[f"{cur['name']}_min"] = self._filter_input_min.text()
            self._filter_values[f"{cur['name']}_max"] = self._filter_input_max.text()

        self._fetch_listings_with_filters(self._collect_filter_params())

    def _fetch_listings_with_filters(self, extra_params):
        """API запрос с текущими фильтрами."""
        self._current_cursor = None
        pool = QThreadPool.globalInstance()
        w = ApiWorker(
            get_item_listings, self.api_key, self.def_index,
            self.paint_index, self.sticker_index, self.category,
            keychain_index=self.keychain_index,
            **extra_params,
        )
        w.signals.result.connect(self._on_listings_loaded)
        w.signals.error.connect(self._on_request_error)
        pool.start(w)

    def _set_label_clear_style(self, label, text, active):
        if active:
            label.setText(f"\u2715 {text}")
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: #E85454; text-align: left; padding: 0 1px;
                }}
                QPushButton:hover {{ color: {Theme.PRIMARY}; }}
            """)
        else:
            label.setText(text)
            label.setCursor(Qt.CursorShape.ArrowCursor)
            label.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: {Theme.TEXT_SECONDARY}; text-align: left; padding: 0 4px;
                }}
            """)

    def _update_clear_labels(self):
        if not self.is_charm:
            float_active = bool(self._float_min.text() or self._float_max.text())
            self._set_label_clear_style(self._float_label, "Float", float_active)

        cur = self._filter_types[self._current_filter_idx]
        if cur["mode"] == "single":
            filter_active = bool(self._filter_input_single.text())
        else:
            filter_active = bool(self._filter_input_min.text() or self._filter_input_max.text())
        filter_name = cur['name'] if self.is_charm else f"{cur['name']} \u25be"
        self._set_label_clear_style(self._filter_label, filter_name, filter_active)

    def _check_filters_active(self):
        cur = self._filter_types[self._current_filter_idx]
        if cur["mode"] == "single":
            self._filter_values[cur["name"]] = self._filter_input_single.text()
        else:
            self._filter_values[f"{cur['name']}_min"] = self._filter_input_min.text()
            self._filter_values[f"{cur['name']}_max"] = self._filter_input_max.text()
        self._update_clear_labels()

    def _clear_float_filter(self):
        self._float_min.clear()
        self._float_max.clear()
        self._update_clear_labels()
        self._apply_filters()

    def _clear_sub_filter(self):
        self._filter_input_single.clear()
        self._filter_input_min.clear()
        self._filter_input_max.clear()
        cur = self._filter_types[self._current_filter_idx]
        if cur["mode"] == "single":
            self._filter_values[cur["name"]] = ""
        else:
            self._filter_values[f"{cur['name']}_min"] = ""
            self._filter_values[f"{cur['name']}_max"] = ""
        self._update_clear_labels()
        self._apply_filters()

    def _on_charm_label_click(self):
        has_value = bool(self._filter_input_min.text() or self._filter_input_max.text())
        if has_value:
            self._clear_sub_filter()

    def _on_filter_label_click(self):
        cur = self._filter_types[self._current_filter_idx]
        if cur["mode"] == "single":
            has_value = bool(self._filter_input_single.text())
        else:
            has_value = bool(self._filter_input_min.text() or self._filter_input_max.text())

        if has_value:
            self._clear_sub_filter()
        else:
            self._filter_selector.exec(
                self._filter_label.mapToGlobal(self._filter_label.rect().bottomLeft())
            )

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

        if not self.has_params:
            cols = ["Price", "Days"]
            col_widths = [140, 133]
        elif self.is_charm:
            cols = ["Pattern", "Price", "Days"]
            col_widths = [100, 80, 93]
        else:
            cols = ["Float", "Seed", "Price", "Days"]
            col_widths = [118, 56, 55, 49]

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
        for col, w in enumerate(col_widths):
            self.listings_table.setColumnWidth(col, w)
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)

        self.listings_table.verticalScrollBar().valueChanged.connect(self._on_listings_scroll)

        lay.addWidget(self.listings_table)
        return frame

    def _on_listings_scroll(self, value):
        sb = self.listings_table.verticalScrollBar()
        if not self._current_cursor or self._is_loading_more:
            return
        if value >= sb.maximum() - 2:
            self._load_more_listings()

    def _load_more_listings(self):
        self._is_loading_more = True
        params = self._collect_filter_params() if self.has_params else {}
        params["cursor"] = self._current_cursor
        pool = QThreadPool.globalInstance()
        w = ApiWorker(
            get_item_listings, self.api_key, self.def_index,
            self.paint_index, self.sticker_index, self.category,
            keychain_index=self.keychain_index,
            **params,
        )
        w.signals.result.connect(self._on_more_listings_loaded)
        w.signals.error.connect(self._on_load_more_error)
        pool.start(w)

    def _on_more_listings_loaded(self, data):
        self._is_loading_more = False
        if not data:
            return
        if isinstance(data, dict):
            self._current_cursor = data.get("cursor")
            new_items = data.get("data", [])
        else:
            new_items = data if isinstance(data, list) else []
            self._current_cursor = None

        if new_items:
            self._listings_data.extend(new_items)
            self.listings_table.setSortingEnabled(False)
            self._append_listings_rows(new_items)
            self.listings_table.setSortingEnabled(True)

    def _on_load_more_error(self, error):
        self._is_loading_more = False
        e, tb = error
        logging.error(f"Load more error: {e}")

    def _get_active_filter_name(self):
        return self._filter_types[self._current_filter_idx]["name"]

    def _populate_listings_table(self, listings):
        self.listings_table.setSortingEnabled(False)
        self.listings_table.setRowCount(0)
        self._append_listings_rows(listings)
        self.listings_table.setSortingEnabled(True)
        # Сортировка по колонке Price
        price_col = self._get_price_col()
        self.listings_table.sortItems(price_col, Qt.SortOrder.AscendingOrder)

    def _get_price_col(self):
        if not self.has_params:
            return 0
        if self.is_charm:
            return 1
        return 2

    def _append_listings_rows(self, listings):
        active_filter = self._get_active_filter_name() if self.has_params else None
        show_pct = active_filter in ("Fade %", "Blue %") if active_filter else False

        for entry in listings:
            row = self.listings_table.rowCount()
            self.listings_table.insertRow(row)

            item = entry.get("item", {})
            price = entry.get("price", 0)
            created = entry.get("created_at", "")

            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                days_val = (datetime.now(timezone.utc) - dt).total_seconds()
            except Exception:
                days_val = 0

            if not self.has_params:
                # Стикеры, кейсы и тп: Price | Days
                price_item = NumericItem(cents_to_dollars(price), price)
                price_item.setForeground(QColor(Theme.PRIMARY))
                price_item.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE, QFont.Weight.Bold))
                self.listings_table.setItem(row, 0, price_item)
                self.listings_table.setItem(row, 1, NumericItem(days_ago(created), days_val))

            elif self.is_charm:
                # Брелки: Pattern | Price | Days
                pattern = item.get("keychain_pattern", 0)
                pat_item = NumericItem(str(pattern), pattern)
                self.listings_table.setItem(row, 0, pat_item)

                price_item = NumericItem(cents_to_dollars(price), price)
                price_item.setForeground(QColor(Theme.PRIMARY))
                price_item.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE, QFont.Weight.Bold))
                self.listings_table.setItem(row, 1, price_item)
                self.listings_table.setItem(row, 2, NumericItem(days_ago(created), days_val))

            else:
                # Скины: Float | Seed | Price | Days
                fv = item.get("float_value", 0)
                seed = item.get("paint_seed", 0)

                float_item = NumericItem(f"{fv:.14f}", fv)
                float_item.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_SMALL))
                self.listings_table.setItem(row, 0, float_item)

                if show_pct:
                    if active_filter == "Fade %":
                        pct_val = (item.get("fade") or {}).get("percentage", 0)
                    else:
                        pct_val = (item.get("blue_gem") or {}).get("playside_blue", 0)
                    col1_item = NumericItem(f"{pct_val:.1f}%", pct_val)
                else:
                    col1_item = NumericItem(str(seed), seed)
                self.listings_table.setItem(row, 1, col1_item)

                price_item = NumericItem(cents_to_dollars(price), price)
                price_item.setForeground(QColor(Theme.PRIMARY))
                price_item.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE, QFont.Weight.Bold))
                self.listings_table.setItem(row, 2, price_item)
                self.listings_table.setItem(row, 3, NumericItem(days_ago(created), days_val))

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

        if not self.has_params:
            sales_cols = ["Price", "Ago"]
            sales_widths = [140, 133]
        elif self.is_charm:
            sales_cols = ["Price", "Pattern", "Ago"]
            sales_widths = [70, 110, 98]
        else:
            sales_cols = ["Price", "Float", "Seed", "Ago"]
            sales_widths = [50, 123, 58, 47]

        self._sales_table = QTableWidget(0, len(sales_cols))
        self._sales_table.setHorizontalHeaderLabels(sales_cols)
        self._sales_table.setStyleSheet(Theme.table_style())
        self._sales_table.horizontalHeader().setStyleSheet(Theme.table_header_style())
        self._sales_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._sales_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._sales_table.verticalHeader().setDefaultSectionSize(28)
        self._sales_table.verticalHeader().setVisible(False)
        self._sales_table.setAlternatingRowColors(True)

        h = self._sales_table.horizontalHeader()
        h.setStretchLastSection(False)
        for col, w in enumerate(sales_widths):
            self._sales_table.setColumnWidth(col, w)
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)

        lay.addWidget(self._sales_table)
        return frame

    def _populate_sales_table(self, sales):
        tbl = self._sales_table
        tbl.setRowCount(0)

        active_filter = self._get_active_filter_name() if self.has_params else None
        show_pct = active_filter in ("Fade %", "Blue %") if active_filter else False

        for sale in sales[:40]:
            r = tbl.rowCount()
            tbl.insertRow(r)

            price = sale.get("price", 0)
            item = sale.get("item", {})
            sold = sale.get("sold_at", "")

            p = QTableWidgetItem(cents_to_dollars(price))
            p.setForeground(QColor(Theme.PRIMARY))
            p.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE, QFont.Weight.Bold))
            tbl.setItem(r, 0, p)

            if not self.has_params:
                # Стикеры, кейсы: Price | Ago
                tbl.setItem(r, 1, QTableWidgetItem(days_ago(sold)))

            elif self.is_charm:
                # Брелки: Price | Pattern | Ago
                pattern = item.get("keychain_pattern", 0)
                tbl.setItem(r, 1, QTableWidgetItem(str(pattern)))
                tbl.setItem(r, 2, QTableWidgetItem(days_ago(sold)))
            else:
                # Скины: Price | Float | Seed | Ago
                fv = item.get("float_value", 0)
                seed = item.get("paint_seed", 0)

                f = QTableWidgetItem(f"{fv:.12f}")
                f.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_SMALL))
                tbl.setItem(r, 1, f)

                if show_pct:
                    if active_filter == "Fade %":
                        pct_val = (item.get("fade") or {}).get("percentage", 0)
                    else:
                        pct_val = (item.get("blue_gem") or {}).get("playside_blue", 0)
                    s = QTableWidgetItem(f"{pct_val:.1f}%")
                else:
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
        for col, w in enumerate([55, 35, 183]):
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

    def _on_listing_double_click(self, row, col):
        price_col = self._get_price_col()
        if col == price_col:
            item = self.listings_table.item(row, price_col)
            if isinstance(item, NumericItem):
                self.price_selected.emit(item._sort_value)

    def _on_sale_double_click(self, row, col):
        if col == 0:
            item = self._sales_table.item(row, 0)
            if item:
                text = item.text().replace("$", "").strip()
                try:
                    cents = int(round(float(text) * 100))
                    self.price_selected.emit(cents)
                except ValueError:
                    pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.setGeometry(self.rect())
        if hasattr(self, '_stats_btn'):
            self._position_settings_btn()
