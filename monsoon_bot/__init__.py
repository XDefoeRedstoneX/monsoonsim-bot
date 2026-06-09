"""MonsoonSim automation bot.

A desktop tool that attaches to a logged-in MonsoonSim browser session and
automates repetitive operations (retail replenishment, service/HR manday
assignment) using Playwright.

The package is intentionally layered so the business logic is testable without
a browser:

* ``products``  - product/location data models (pure)
* ``planning``  - replenishment order maths (pure)
* ``parsing``   - DOM-text parsing helpers (pure)
* ``driver``    - the Playwright engine (browser-bound)
* ``app``       - the Tkinter GUI
"""

__version__ = "2.0.0"
