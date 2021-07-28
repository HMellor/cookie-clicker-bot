# Cookie Clicker Bot
A bot I made as a learning exercise that automates the browser game [Cookie Clicker](https://orteil.dashnet.org/cookieclicker/).

It makes use of my [`selenium_tools`](https://github.com/HMellor/selenium-tools) package as well as `asyncio`.

## The Strategy
1. Click the big cookie as fast as possible
2. Click the golden cookie whenever it appears
3. If you can afford an upgrade, buy it
4. Purchase buildings:
   1. Find the best value building (additional CpS per C spent), buy as many as possible
   2. If the next new building type costs less than 3x your balance, save up and buy it

## Installation
```bash
git clone https://github.com/HMellor/cookie-clicker-bot
cd cookie-clicker-bot
pip install -r requirements.txt
```
Download the uBlock Origin extension to the [extensions](extensions) folder.

## Usage
```python
python bot.py
```