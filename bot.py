import os
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
            elem.click()
            await asyncio.sleep(0)

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
                if golden_cookie is not None:
                    golden_cookie.click()
                    self.logger.info("Got the golden cookie!")
                await asyncio.sleep(1)
            except ElementNotInteractableException as e:
                # refresh the golden cookie container
                self.logger.error(e.msg.replace("\n", " ").strip())
                self.logger.warning("Golden cookie failed")
            except ElementClickInterceptedException as e:
                self.logger.error(e.msg.replace("\n", " ").strip())
                self.logger.warning("Golden cookie failed, it was likely under the tooltip")

    async def check_products(self):
        while True:
            products = self.update_all_products(iterative=True)
            # find most cost effective option
            current_values = self.current_values.items()
            none_owned = [v for v in current_values if v[1]["owned"] == 0]
            # extract salient products
            best = max(current_values, key=lambda i: i[1]["value"])[1]
            cheapest_none_owned = min(none_owned, key=lambda i: i[1]["price"])[1]
            # if we have enough cookies to work towards the next building, do it
            balance = self.__get_balance()
            if len(none_owned) and cheapest_none_owned["price"] < balance * 3:
                best = cheapest_none_owned
                self.logger.info(
                    f"Going for new building: {best['name']}, {100*balance/best['price']:.2f}% complete"
                )
            products[best["index"]].click()
            # update current values after purchase
            self.__update_product_record(best)
            await asyncio.sleep(60)

    async def check_upgrades(self):
        while True:
            try:
                upgrades = self.__get_upgrade_list()
                cheapest_upgrade = upgrades[0]
                metadata = self.get_upgrade_metadata(cheapest_upgrade)
                if "enabled" in metadata["classes"]:
                    self.logger.info(f"Buying cheapest upgrade")
                    cheapest_upgrade.click()
                    self.logger.info("Updating all product values")
                    _ = self.update_all_products(iterative=False)
            except StaleElementReferenceException:
                self.logger.warning("Upgrade failed.")

            await asyncio.sleep(60)

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

    def __update_product_record(self, metadata):
        self.__update_tooltip(metadata["index"])
        data = self.get_product_data()
        product_record = {metadata["name"]: {**metadata, **data}}
        self.current_values.update(product_record)

    def start(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.click_forever(self.big_cookie))
        loop.create_task(self.click_golden_cookie())
        loop.create_task(self.check_products())
        loop.create_task(self.check_upgrades())
        loop.run_forever()

    def text2float(self, text: str):
        if not len(text):
            self.logger.warning("Input string is empty")
            return 0
        parts = text.lower().replace(",", "").split(" ")
        mapping = {
            "million": 10 ** 6,
            "billion": 10 ** 9,
            "trillion": 10 ** 12,
            "quadrillion": 10 ** 15,
            "quintillion": 10 ** 18,
            "sextillion": 10 ** 21,
            "septillion": 10 ** 24,
        }
        if parts[0][-1] == "%":
            return float(parts[0][:-1]) / 100
        n = len(parts)
        if n == 1:
            return float(parts[0])
        elif n == 2:
            return float(parts[0]) * mapping[parts[1]]

    def get_product_data(self):
        try:
            tooltip = selector.find_element(
                "id", "tooltip", self.chrome_browser.driver, "located"
            )
            price_text = selector.find_element(
                "class", "price", tooltip, "located"
            ).text
            owned_text = selector.find_element("tag", "small", tooltip, "located").text
            stats_elems = selector.find_element(
                "css", ".data > b", tooltip, "all_located", ignore_timeout=True
            )
            assert bool(price_text) and bool(owned_text)
            price = self.text2float(price_text)
            owned = int(owned_text.split(" ")[-1])
            value = 0
            cps = 0
            if owned > 0:
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
            return data
        except (StaleElementReferenceException, AssertionError):
            return self.get_product_data()

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
