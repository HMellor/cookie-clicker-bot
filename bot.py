import os
import math
import asyncio
import logging
import logging.handlers
from pathlib import Path
from selenium_tools import browser, selector
from selenium.common.exceptions import (
    StaleElementReferenceException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
)


class CookieClicker:
    golden_cookie_sleep_seconds = 1
    big_cookie_sleep_seconds = 0
    check_purchase_sleep_seconds = 60
    wrinkler_sleep_seconds = 5
    mapping = {
        "cookies": 1,
        "thousand": 10 ** 3,
        "million": 10 ** 6,
        "billion": 10 ** 9,
        "trillion": 10 ** 12,
        "quadrillion": 10 ** 15,
        "quintillion": 10 ** 18,
        "sextillion": 10 ** 21,
        "septillion": 10 ** 24,
        "octillion": 10 ** 27,
        "nonillion": 10 ** 30,
        "decillion": 10 ** 33,
        "undecillion": 10 ** 36,
        "duodecillion": 10 ** 39,
        "tredecillion": 10 ** 42,
        "quattuordecillion": 10 ** 45,
        "quindecillion": 10 ** 48,
        "sexdecillion": 10 ** 51,
        "septendecillion": 10 ** 54,
        "octodecillion": 10 ** 57,
        "novemdecillion": 10 ** 60,
        "vigintillion": 10 ** 63,
    }

    def __init__(self):
        self.current_values = {}
        self.logger = self.configure_logger()
        self.chrome_browser = self.open_browser()
        self.chrome_browser.navigate_to("https://orteil.dashnet.org/cookieclicker/")
        self.big_cookie = selector.find_element(
            "id", "bigCookie", self.chrome_browser.driver, "located"
        )
        self.golden_cookie_container = selector.find_element(
            "id", "shimmers", self.chrome_browser.driver, "located"
        )
        self.upgrades_container = selector.find_element(
            "id", "upgrades", self.chrome_browser.driver, "located"
        )
        self.products_container = selector.find_element(
            "id", "products", self.chrome_browser.driver, "located"
        )

    def __del__(self):
        self.chrome_browser.close()

    def open_browser(self):
        # create data directory if it doesn't exist
        data_dir = Path(__file__).parent / "data"
        if not data_dir.exists():
            os.mkdir(data_dir)
        # instantiate the browser
        chrome_browser = browser.Browser(
            "chrome",
            headless=False,
            extensions=[Path("extensions/ublock").absolute()],
            user_data_dir="data/cookie_clicker_data",
        )
        return chrome_browser

    def configure_logger(self):
        logger = logging.getLogger("cookie_clicker_bot")
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        log_dir = Path(__file__).parent / "logs"
        if not log_dir.exists():
            os.mkdir(log_dir)
        log_path = log_dir / "bot.log"
        fh = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1000000, backupCount=5
        )
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

    async def click_forever(self, elem):
        while True:
            try:
                elem.click()
            except ElementClickInterceptedException as e:
                self.logger.error(
                    "Golden cookie blocking big cookie: "
                    + e.msg.replace("\n", " ").strip()
                )
                await asyncio.sleep(self.golden_cookie_sleep_seconds)
            await asyncio.sleep(self.big_cookie_sleep_seconds)

    async def click_golden_cookie(self):
        while True:
            try:
                golden_cookie = selector.find_element(
                    "class",
                    "shimmer",
                    self.golden_cookie_container,
                    "located",
                    wait=0,
                    ignore_timeout=True,
                )
                # check that golden cookie is not negative (ruin)
                if (
                    golden_cookie
                    and golden_cookie.get_attribute("alt") == "Golden cookie"
                ):
                    golden_cookie.click()
                    self.logger.info("Got the golden cookie!")
            except (
                ElementNotInteractableException,
                ElementClickInterceptedException,
                StaleElementReferenceException,
            ) as e:
                self.logger.error(
                    "Golden cookie failed: " + e.msg.replace("\n", " ").strip()
                )
            await asyncio.sleep(self.golden_cookie_sleep_seconds)

    async def pop_wrinkler(self):
        while True:
            self.__pop_wrinkler()
            await asyncio.sleep(self.wrinkler_sleep_seconds)

    async def check_purchases(self):
        while True:
            self.buy_upgrades()
            self.buy_products()
            await asyncio.sleep(self.check_purchase_sleep_seconds)

    def buy_upgrades(self):
        upgrades = self.__get_upgrade_list()
        cheapest_upgrade = upgrades[0]
        metadata = self.get_upgrade_metadata(cheapest_upgrade)
        update_products = False
        if "enabled" in metadata["classes"]:
            self.logger.info("Buying cheapest upgrade and updating all product values")
            cheapest_upgrade.click()
            update_products = True

        buy_all_btn_present = selector.find_element(
            "id",
            "storeBuyAllButton",
            self.upgrades_container,
            "located",
            wait=0,
            ignore_timeout=True,
        )
        if buy_all_btn_present:
            self.__buy_all_upgrades()
        if update_products:
            _ = self.update_all_products(iterative=False)

    def buy_products(self):
        products = self.update_all_products(iterative=True)
        # find most cost effective option
        current_values = self.current_values.items()
        none_owned = [v for v in current_values if v[1]["owned"] == 0]
        # extract salient products
        best = max(current_values, key=lambda i: i[1]["value"])[1]
        if len(none_owned):
            cheapest_none_owned = min(none_owned, key=lambda i: i[1]["price"])[1]
        # if we have enough cookies to work towards the next building, do it
        balance = self.__get_balance()
        if len(none_owned) and cheapest_none_owned["price"] < balance * 3:
            best = cheapest_none_owned
            self.logger.info(
                f"Going for new building: {best['name']}, {100*balance/best['price']:.2f}% complete"
            )
        # cumulative cost equation: {\displaystyle {\text{Cumulative price}}={\frac {{\text{Base cost}}\times (1.15^{N}-1)}{0.15}}}
        can_afford = math.floor(math.log((balance * 0.15 / best["price"]) + 1, 1.15))
        final_owned = best["owned"] + can_afford
        for _ in range(can_afford):
            products[best["index"]].click()
        # update current values after purchase
        self.__update_product_record(best)
        existing_purchase = best["value"] > self.current_values[best["name"]]["value"]
        new_purchase = best["owned"] == 0
        if (existing_purchase or new_purchase) and can_afford:
            plural = "s" if can_afford > 1 else ""
            self.logger.info(
                f"Bought {can_afford} {best['name']}{plural} ({final_owned} now owned) with initial value of {best['value']:.3E} CpS per C"
            )

    def __get_product_list(self):
        return selector.find_element(
            "class",
            "product",
            self.products_container,
            "all_located",
            wait=0,
            ignore_timeout=True,
        )

    def __get_balance(self) -> float:
        balance_text = selector.find_element(
            "id", "cookies", self.chrome_browser.driver, "located"
        ).text
        return self.text2float(balance_text.split("\n")[0])

    def __get_upgrade_list(self):
        return selector.find_element(
            "class",
            "upgrade",
            self.upgrades_container,
            "all_located",
            wait=0,
            ignore_timeout=True,
        )

    def __update_tooltip(self, index):
        self.chrome_browser.driver.execute_script(
            f"Game.tooltip.dynamic=1;Game.tooltip.draw(this,function(){{return Game.ObjectsById[{index}].tooltip();}},'store');Game.tooltip.wobble();"
        )

    def __hide_tooltip(self):
        self.chrome_browser.driver.execute_script("Game.tooltip.shouldHide=1;")

    def __pop_wrinkler(self):
        self.chrome_browser.driver.execute_script("Game.PopRandomWrinkler();")

    def __buy_all_upgrades(self):
        self.chrome_browser.driver.execute_script("Game.storeBuyAll();")

    def __update_product_record(self, metadata):
        data = self.get_product_data(metadata["index"])
        product_record = {metadata["name"]: {**metadata, **data}}
        self.current_values.update(product_record)

    def start(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.click_forever(self.big_cookie))
        loop.create_task(self.click_golden_cookie())
        loop.create_task(self.pop_wrinkler())
        loop.create_task(self.check_purchases())
        loop.run_forever()

    def text2float(self, text: str):
        if not len(text):
            self.logger.warning("Input string is empty")
            return 0
        parts = text.lower().replace(",", "").split(" ")
        if parts[0][-1] == "%":
            return float(parts[0][:-1]) / 100
        n = len(parts)
        if n == 1:
            return float(parts[0])
        elif n == 2:
            return float(parts[0]) * self.mapping[parts[1]]

    def get_product_data(self, index):
        try:
            self.__update_tooltip(index)
            tooltip = selector.find_element(
                "id", "tooltip", self.chrome_browser.driver, "located"
            )
            price = selector.find_element("class", "price", tooltip, "located")
            owned = selector.find_element("tag", "small", tooltip, "located")
            assert bool(price) and bool(owned)
            price_text = price.text
            owned_text = owned.text
            assert bool(price_text) and bool(owned_text)
            price = self.text2float(price_text)
            owned = int(owned_text.split(" ")[-1])
            value = 0
            cps = 0
            if owned > 0:
                stats_elems = selector.find_element(
                    "css", ".data > b", tooltip, "all_located", ignore_timeout=True
                )
                stats_text = [i.text for i in stats_elems]
                assert all([bool(i) for i in stats_text])
                stats = [self.text2float(e) for e in stats_text]
                if len(stats) == 6:
                    cps = (stats[0]) + ((stats[3]) / owned)
                elif len(stats) == 4:
                    cps = stats[0]
                else:
                    self.logger.error("Unknown tooltip format.")
                value = cps / price
            data = {
                "price": price,
                "value": value,
                "owned": owned,
                "cps": cps,
            }
            self.__hide_tooltip()
            return data
        except (StaleElementReferenceException, AssertionError):
            return self.get_product_data(index)

    def get_product_metadata(self, product):
        product_classes = set(product.get_attribute("class").split(" "))
        product_id = product.get_attribute("id")
        product_idx = int(product_id.replace("product", ""))
        product_name = selector.find_element("class", "title", product, "located").text
        metadata = {
            "name": product_name,
            "classes": product_classes,
            "index": product_idx,
        }
        return metadata

    def get_upgrade_metadata(self, upgrade):
        upgrade_classes = set(upgrade.get_attribute("class").split(" "))
        upgrade_id = upgrade.get_attribute("id")
        upgrade_idx = int(upgrade_id.replace("upgrade", ""))
        metadata = {
            "classes": upgrade_classes,
            "index": upgrade_idx,
        }
        return metadata

    def update_all_products(self, iterative=False):
        products = self.__get_product_list()
        for product in products:
            metadata = self.get_product_metadata(product)
            if "toggledOff" in metadata["classes"]:
                continue
            # update current values
            is_new = metadata["name"] not in self.current_values
            if not iterative or is_new:
                self.__update_product_record(metadata)
        return products


if __name__ == "__main__":
    cookie_clicker = CookieClicker()
    try:
        cookie_clicker.start()
    finally:
        del cookie_clicker
