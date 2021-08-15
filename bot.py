import os
import math
import asyncio
import logging
import logging.handlers
from pathlib import Path
from selenium_tools import browser as b
from selenium_tools import selector as s
from selenium.common.exceptions import (
    StaleElementReferenceException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
)

mapping = {
    "cookies": 1,
    "thousand": 1e3,
    "million": 1e6,
    "billion": 1e9,
    "trillion": 1e12,
    "quadrillion": 1e15,
    "quintillion": 1e18,
    "sextillion": 1e21,
    "septillion": 1e24,
    "octillion": 1e27,
    "nonillion": 1e30,
    "decillion": 1e33,
    "undecillion": 1e36,
    "duodecillion": 1e39,
    "tredecillion": 1e42,
    "quattuordecillion": 1e45,
    "quindecillion": 1e48,
    "sexdecillion": 1e51,
    "septendecillion": 1e54,
    "octodecillion": 1e57,
    "novemdecillion": 1e60,
    "vigintillion": 1e63,
}


def text2float(text: str) -> float:
    if not len(text):
        logger.warning("Input string is empty")
        return 0
    parts = text.lower().replace(",", "").split(" ")
    if parts[0][-1] == "%":
        return float(parts[0][:-1]) / 100
    n = len(parts)
    if n == 1:
        return float(parts[0])
    elif n == 2:
        return float(parts[0]) * mapping[parts[1]]


def configure_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    log_dir = Path(__file__).parent / "logs"
    if not log_dir.exists():
        os.mkdir(log_dir)
    log_path = log_dir / "bot.log"
    fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=1000000, backupCount=5)
    ch.setLevel(logging.INFO)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


class AsyncRunner:
    def __init__(self, tasks, immediate_start=False):
        self.logger = logging.getLogger("bot.AsyncRunner")
        self.tasks = tasks
        if immediate_start:
            self.start()

    async def loop_forever(self, funcs, delay):
        while True:
            try:
                for f in funcs:
                    f()
            except Exception as e:
                self.logger.exception(e)
            await asyncio.sleep(delay)

    def start(self):
        loop = asyncio.get_event_loop()
        for funcs, delay in self.tasks:
            loop.create_task(self.loop_forever(funcs, delay))
        loop.run_forever()


class CookieClicker:
    # Sleep times in seconds
    golden_cookie_sleep = 1
    big_cookie_sleep = 0
    check_buy_sleep = 60
    extras_sleep = 5

    def __init__(self):
        self.products = {}
        self.upgrades = {}
        self.logger = logging.getLogger("bot.CookieClicker")
        self.browser = self.open_browser()
        self.browser.navigate_to("https://orteil.dashnet.org/cookieclicker/")
        self.big_cookie = self.find_by_id("bigCookie")
        self.golden_cookie_container = self.find_by_id("shimmers")
        self.upgrades_container = self.find_by_id("upgrades")
        self.products_container = self.find_by_id("products")
        tasks = [
            ([self.click_big_cookie], self.big_cookie_sleep),
            ([self.click_golden_cookie], self.golden_cookie_sleep),
            ([self.pop_wrinkler, self.click_fortune], self.extras_sleep),
            ([self.buy_upgrades, self.buy_products], self.check_buy_sleep),
        ]
        self.async_runner = AsyncRunner(tasks, immediate_start=True)

    def __del__(self):
        self.browser.close()

    def open_browser(self):
        # create data directory if it doesn't exist
        data_dir = Path(__file__).parent / "data"
        if not data_dir.exists():
            os.mkdir(data_dir)
        # instantiate the browser
        browser = b.Browser(
            "chrome",
            headless=False,
            extensions=[Path("extensions/ublock").absolute()],
            user_data_dir="data/cookie_clicker_data",
        )
        return browser

    def click_big_cookie(self):
        try:
            self.big_cookie.click()
        except ElementClickInterceptedException as e:
            self.log_error("Golden cookie blocking big cookie", e)
            # await asyncio.sleep(self.golden_cookie_sleep)

    def click_golden_cookie(self):
        try:
            golden_cookie = self.__get_golden_cookie()
            # check that golden cookie is not negative
            if golden_cookie:
                golden_cookie_type = golden_cookie.get_attribute("alt")
                if golden_cookie_type != "Wrath cookie":
                    golden_cookie.click()
                    self.logger.info(f"Got the {golden_cookie_type.lower()}!")
        except (
            ElementNotInteractableException,
            ElementClickInterceptedException,
            StaleElementReferenceException,
        ) as e:
            self.log_error("Golden cookie failed", e)

    def buy_upgrades(self):
        upgrades = self.update_all_items("upgrade", iterative=True)
        affordable = [
            u[1] for u in self.upgrades.items() if "enabled" in u[1]["classes"]
        ]
        if len(affordable) > 0:
            upgrades[0].click()
            self.logger.info(f"Bought {affordable[0]['name']}")
            if len(affordable) > 1:
                buy_all_btn_present = self.__get_buy_all_button()
                if buy_all_btn_present:
                    self.logger.info("Buying all remaining affordable upgrades")
                    self.__buy_all_upgrades()
            self.logger.info("Updating all product values")
            self.upgrades = {}
            _ = self.update_all_items("product", iterative=False)

    def buy_products(self):
        products = self.update_all_items("product", iterative=True)
        # find most cost effective option
        none_owned = [p[1] for p in self.products.items() if p[1]["owned"] == 0]
        # extract salient products
        best = max(self.products.items(), key=lambda i: i[1]["value"])[1]
        # if we have enough cookies to work towards the next building, do it
        balance = self.__get_balance()
        if len(none_owned) and none_owned[0]["price"] < balance * 3:
            best = none_owned[0]
            self.logger.info(
                f"Going for new building: {best['name']}, {100*balance/best['price']:.2f}% complete"
            )
        # cumulative cost equation: {\displaystyle {\text{Cumulative price}}={\frac {{\text{Base cost}}\times (1.15^{N}-1)}{0.15}}}
        can_afford = math.floor(math.log((balance * 0.15 / best["price"]) + 1, 1.15))
        final_owned = best["owned"] + can_afford
        for _ in range(can_afford):
            products[best["index"]].click()
        if can_afford:
            # update current values after purchase
            best_data = self.get_tooltip_data(best["index"], "product")
            self.products[best["name"]].update(best_data)
            plural = "s" if can_afford > 1 else ""
            self.logger.info(
                f"Bought {can_afford} {best['name']}{plural} ({final_owned} now owned) with initial value of {best['value']:.3E} CpS per C"
            )

    # Getters
    def find_store_items(self, cls):
        args = ("class", cls, eval(f"self.{cls}s_container"), "all_located", 0, True)
        return s.find_element(*args)

    def __get_golden_cookie(self):
        args = ("class", "shimmer", self.golden_cookie_container, "located", 0, True)
        return s.find_element(*args)

    def __get_buy_all_button(self):
        args = ("id", "storeBuyAllButton", self.upgrades_container, "located", 0, True)
        return s.find_element(*args)

    def __get_balance(self) -> float:
        balance_text = self.find_by_id("cookies").text
        return text2float(balance_text.split("\n")[0])

    # Run JS functions
    def run_js(self, js):
        self.browser.driver.execute_script(js)

    def __update_tooltip(self, index, item_type="product"):
        if item_type == "product":
            func = f"return Game.ObjectsById[{index}].tooltip();"
        elif item_type == "upgrade":
            func = f"return Game.crateTooltip(Game.UpgradesById[{index}],'store');"
        else:
            raise ValueError
        self.run_js(f"Game.tooltip.draw(this,function(){{{func}}},'store');")

    def __hide_tooltip(self, item_type="product"):
        if item_type == "product":
            self.run_js("Game.tooltip.shouldHide=1;")
        elif item_type == "upgrade":
            self.run_js("Game.setOnCrate(0);Game.tooltip.shouldHide=1;")

    def pop_wrinkler(self):
        self.run_js("Game.PopRandomWrinkler();")

    def __buy_all_upgrades(self):
        self.run_js("Game.storeBuyAll();")

    # Helper functions
    def log_error(self, msg, exc):
        exc_msg = exc.msg.replace("\n", " ").strip()
        self.logger.error(f"{msg}: {exc_msg}")

    def click_fortune(self):
        args = ("class", "fortune", self.browser.driver, "located", 0, True)
        fortune = s.find_element(*args)
        if fortune:
            try:
                fortune.click()
            except ElementClickInterceptedException as e:
                self.log_error("Fortune cookie failed", e)
            self.logger.info("Got fortune cookie!")

    def get_tooltip_data(self, index, item_type):
        self.__update_tooltip(index, item_type=item_type)
        tooltip = s.find_element("id", "tooltip", self.browser.driver, "located")
        name = s.find_element("class", "name", tooltip, "located")
        price = s.find_element("class", "price", tooltip, "located")
        owned = s.find_element("tag", "small", tooltip, "located", 0, True)
        try:
            name = name.text if name else name
            price = text2float(price.text) if price else price
            owned = int(owned.text.split(" ")[-1]) if owned else owned
            value, cps = None, None
            if owned and owned > 0:
                stats_elems = s.find_element("css", ".data > b", tooltip, "all_located")
                assert bool(stats_elems)
                stats_text = [i.text for i in stats_elems]
                assert all([bool(i) for i in stats_text])
                stats = [text2float(e) for e in stats_text]
                if len(stats) == 6:
                    cps = (stats[0]) + ((stats[3]) / owned)
                elif len(stats) == 4:
                    cps = stats[0]
                else:
                    self.logger.error("Unknown tooltip format.")
                value = cps / price
            keys = ["name", "price", "owned", "value", "cps"]
            data = {}
            for k in keys:
                if v := eval(k):
                    data[k] = v
            self.__hide_tooltip(item_type)
            return data
        except (StaleElementReferenceException, AssertionError):
            return self.get_tooltip_data(index, item_type)

    def get_item_metadata(self, item):
        classes = set(item.get_attribute("class").split(" "))
        hover_js = item.get_attribute("onmouseover")
        index = int(hover_js.split("[")[1].split("]")[0])
        name = s.find_element("class", "title", item, "located", 0, True)
        metadata = {"classes": classes, "index": index}
        if name:
            metadata["name"] = name.text
        return metadata

    def find_by_id(self, id):
        return s.find_element("id", id, self.browser.driver, "located")

    def update_all_items(self, item_type, iterative=False):
        items = self.find_store_items(item_type)
        for item in items:
            data = self.get_item_metadata(item)
            if "toggledOff" not in data["classes"]:
                data.update(self.get_tooltip_data(data["index"], item_type))
                # update stored item data
                is_new = data["name"] not in eval(f"self.{item_type}s")
                if not iterative or is_new:
                    eval(f"self.{item_type}s").update({data["name"]: data})
        return items


if __name__ == "__main__":
    logger = configure_logger("bot")
    cookie_clicker = CookieClicker()
    try:
        cookie_clicker.start()
    finally:
        del cookie_clicker
