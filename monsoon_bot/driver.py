"""Playwright-based engine for driving a live MonsoonSim session.

This replaces the old ``game_api.py`` (which used the abandoned ``pyppeteer``)
with the actively-maintained Playwright async API. All game state lives on the
``MonsoonDriver`` instance instead of module-level globals, so switching product
or location sets no longer mutates shared state.

Connection model is unchanged: we attach over the Chrome DevTools Protocol to an
already-running Chrome that was started with ``--remote-debugging-port=9222``.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from . import selectors as S
from .parsing import parse_day, parse_space, parse_stock
from .planning import plan_replenishment
from .products import ProductSet

DEFAULT_TIMEOUT_MS = 5000


# --- Connection ---------------------------------------------------------------
@dataclass
class GameConnection:
    """Holds the Playwright objects so the app can cleanly shut them down."""
    playwright: object
    browser: object
    page: object

    async def close(self) -> None:
        try:
            await self.browser.close()
        except Exception:
            pass
        try:
            await self.playwright.stop()
        except Exception:
            pass


def _find_game_page(browser, site_fragments: list[str]):
    for context in browser.contexts:
        for page in context.pages:
            url = page.url or ""
            if any(fragment in url for fragment in site_fragments):
                return page
    return None


async def connect_to_game(settings: dict) -> GameConnection:
    """Attach to the running Chrome and locate the MonsoonSim tab."""
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(settings["browser_url"])
    except Exception as exc:
        await playwright.stop()
        raise RuntimeError(
            f"Could not connect to Chrome at {settings['browser_url']}. "
            "Is Chrome running with --remote-debugging-port=9222? "
            f"(details: {exc})"
        ) from exc

    page = _find_game_page(browser, settings["site_fragments"])
    if page is None:
        await browser.close()
        await playwright.stop()
        raise RuntimeError(
            "Connected to Chrome, but no MonsoonSim tab was found. "
            "Open and log in to the game first."
        )
    return GameConnection(playwright=playwright, browser=browser, page=page)


# --- Driver -------------------------------------------------------------------
class MonsoonDriver:
    """High-level automation API over a single MonsoonSim page."""

    def __init__(self, page, product_set: ProductSet, location_map: dict[str, str],
                 settings: dict):
        self.page = page
        self.product_set = product_set
        self.location_map = location_map
        self.settings = settings
        self.timeout = int(settings.get("element_timeout_ms", DEFAULT_TIMEOUT_MS))
        self.location_set_name = settings.get("default_location_set", "")

    # --- low-level primitives ---
    async def _find(self, selector: str, timeout: int | None = None):
        timeout = self.timeout if timeout is None else timeout
        try:
            return await self.page.wait_for_selector(selector, timeout=timeout)
        except Exception as exc:
            raise RuntimeError(f"Could not find element '{selector}': {exc}") from exc

    async def _click(self, selector: str, timeout: int | None = None) -> None:
        timeout = self.timeout if timeout is None else timeout
        await self.page.click(selector, timeout=timeout)

    async def _js_click(self, selector: str) -> None:
        """Trigger a click via JS — useful for elements that resist real clicks."""
        await self.page.wait_for_selector(selector, timeout=self.timeout)
        if selector.startswith("xpath="):
            xpath = selector[len("xpath="):]
            await self.page.evaluate(
                "(xp) => document.evaluate(xp, document, null, "
                "XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click()",
                xpath,
            )
        else:
            await self.page.evaluate("(sel) => document.querySelector(sel).click()", selector)

    async def _check_for_rate_limit(self) -> bool:
        """True if the game's 'Slow down, you click too fast' notice is showing."""
        try:
            content = await self.page.evaluate("() => document.body.textContent")
            return "Slow down, you click too fast" in (content or "")
        except Exception:
            return False

    # --- day tracking ---
    async def get_current_day(self) -> dict[str, int]:
        element = await self._find(S.KPI_DAY)
        text = await element.text_content()
        current, total = parse_day(text or "")
        return {"current": current, "total": total}

    async def wait_for_next_day(self, current_day_num: int) -> dict[str, int]:
        timeout = int(self.settings.get("next_day_timeout_seconds", 45))
        for _ in range(timeout):
            day_info = await self.get_current_day()
            if day_info["current"] > current_day_num:
                return day_info
            await asyncio.sleep(1)
        raise RuntimeError("Timeout: the in-game day did not advance.")

    # --- service / HR module ---
    _SERVICE_HELPERS_JS = """
    () => {
        window.__mb_forceOpenTab = function (tabName) {
            const tabs = document.querySelectorAll(".ui-tabs-tab");
            tabs.forEach(t => t.classList.remove('ui-tabs-active', 'ui-state-active'));
            const selected = [...tabs].find(t => t.textContent.includes(tabName));
            if (selected) {
                selected.classList.add('ui-tabs-active', 'ui-state-active');
                const panelId = selected.querySelector("a").getAttribute("href");
                document.querySelectorAll(".ui-tabs-panel").forEach(p => p.style.display = 'none');
                document.querySelector(panelId).style.display = 'block';
            }
        };
        window.__mb_clickButtonsForTab = function (tabName, requiredClicks) {
            window.__mb_forceOpenTab(tabName);
            return new Promise(resolve => setTimeout(() => {
                const tabId = jQuery('.ui-tabs-tab').filter(function () {
                    return jQuery(this).text().trim() === tabName;
                }).attr('aria-controls');
                if (!tabId) return resolve();
                const buttons = jQuery('#' + tabId).find('.circle.thecb').not('.disabled').slice(0, requiredClicks);
                buttons.each(function () { jQuery(this).trigger('click'); });
                resolve();
            }, 300));
        };
    }
    """

    async def handle_service_requests(self) -> str:
        """Open the first incoming service request and auto-assign mandays."""
        max_retries = int(self.settings.get("max_retries", 3))
        wait_s = float(self.settings.get("rate_limit_wait_seconds", 1.5))

        for _attempt in range(max_retries):
            try:
                try:
                    await self._click(S.SERVICE_MODULE_BOX)
                    await self._click(S.SERVICE_INCOMING_MENU)
                    await asyncio.sleep(1)
                except Exception:
                    return "Service module not found or not enabled. Skipping."

                try:
                    link = await self._find(S.SERVICE_REQUEST_LINK, timeout=2000)
                    await link.click()
                    await self.page.wait_for_selector(S.FACEBOX_SUBMIT, state="visible",
                                                      timeout=self.timeout)
                except Exception:
                    return "No new service requests found."

                await self.page.evaluate(self._SERVICE_HELPERS_JS)

                mandays = await self.page.evaluate(
                    """() => {
                        const out = [];
                        document.querySelectorAll('.col-md-5').forEach(el => {
                            const m = el.textContent.match(/Required Mandays\\s*:\\s*(\\d+)/);
                            if (m) out.push(parseInt(m[1]));
                        });
                        return out;
                    }"""
                )

                tab_names = ["Marketing Srv", "Franchise Srv", "Technical Srv"]
                for idx, tab_name in enumerate(tab_names):
                    if idx < len(mandays) and mandays[idx] > 0:
                        await self.page.evaluate(
                            "([t, n]) => window.__mb_clickButtonsForTab(t, n)",
                            [tab_name, mandays[idx]],
                        )
                        await asyncio.sleep(0.3)

                await asyncio.sleep(0.5)
                await self._click(S.FACEBOX_SUBMIT)
                await self.page.wait_for_selector(S.FACEBOX, state="hidden", timeout=self.timeout)
                return f"Service request handled (mandays: {mandays or 'none'})."

            except Exception as exc:
                if await self._check_for_rate_limit():
                    await asyncio.sleep(wait_s)
                    continue
                return f"Service request failed: {exc}"

        return f"Service request failed after {max_retries} attempts."

    # --- retail module ---
    async def get_retail_space_info(self, location_name: str) -> dict[str, int]:
        element = await self._find(S.retail_space_xpath(location_name))
        text = await element.text_content()
        try:
            used, total = parse_space(text or "")
        except ValueError as exc:
            raise RuntimeError(f"Could not read space info for '{location_name}': {exc}") from exc
        return {"used_m2": used, "total_m2": total}

    async def get_owned_retail_locations(self) -> list[str]:
        return await self.page.evaluate(
            """(sel) => Array.from(document.querySelectorAll(sel))
                .map(el => el.textContent.replace("Retail", "").replace(/\\u00A0/g, ' ').trim())""",
            S.RETAIL_KPI_TITLES,
        )

    async def get_all_retail_stock(self, location_name: str) -> dict[str, int]:
        stock: dict[str, int] = {}
        for product_name in self.product_set.names:
            element = await self._find(S.retail_stock_xpath(location_name, product_name))
            text = await element.text_content()
            stock[product_name] = parse_stock(text or "0")
        return stock

    async def calculate_replenish_order(self, location_name: str, prioritized: list[str],
                                        target_fill_percentage: float = 100) -> dict[str, int]:
        """Dry run: read the location's space + stock and return the planned order."""
        space = await self.get_retail_space_info(location_name)
        stock = await self.get_all_retail_stock(location_name)
        return plan_replenishment(
            self.product_set, stock, space["used_m2"], space["total_m2"],
            prioritized, target_fill_percentage,
        )

    async def procure_for_retail_location(self, location_name: str, prioritized: list[str],
                                          target_fill_percentage: float = 100,
                                          vendor_name: str | None = None) -> str:
        """Calculate and actually place a replenishment order, with retries."""
        vendor_name = vendor_name or self.settings.get("default_vendor", "VFG2")
        max_retries = int(self.settings.get("max_retries", 3))
        wait_s = float(self.settings.get("rate_limit_wait_seconds", 1.5))

        for _attempt in range(max_retries):
            try:
                orders = await self.calculate_replenish_order(
                    location_name, prioritized, target_fill_percentage)
                if not orders:
                    return "Analysis complete. No order needed to meet targets."

                location_id = self.location_map.get(location_name)
                if not location_id:
                    return (
                        f"SKIPPED {location_name}: not found in the "
                        f"'{self.location_set_name}' location map. Check Global Settings."
                    )

                await self._click(S.RETAIL_MODULE_BOX)
                await self._click(S.RETAIL_VENDOR_MENU)
                await self._js_click(S.vendor_buy_xpath(vendor_name))
                await self.page.wait_for_selector(S.FACEBOX_SUBMIT, state="visible",
                                                  timeout=self.timeout)

                await self.page.select_option(S.RETAIL_DESTINATION_SELECT, location_id)
                for product_name, quantity in orders.items():
                    code = self.product_set.code_of(product_name)
                    if not code:
                        continue
                    await self.page.select_option(S.product_qty_select(code), str(quantity))

                await self._click(S.FACEBOX_SUBMIT)
                await self.page.wait_for_selector(S.FACEBOX, state="hidden", timeout=self.timeout)

                summary = ", ".join(f"{qty} of {prod}" for prod, qty in orders.items())
                return f"Successfully ordered: {summary} for {location_name}."

            except Exception as exc:
                if await self._check_for_rate_limit():
                    await asyncio.sleep(wait_s)
                    continue
                return f"SKIPPED {location_name}: could not process replenishment. Reason: {exc}"

        return f"SKIPPED {location_name}: failed after {max_retries} attempts."

    # --- diagnostics ---
    async def self_test(self) -> list[tuple[str, bool, str]]:
        """Run quick health checks and return (check_name, ok, detail) rows."""
        results: list[tuple[str, bool, str]] = []

        results.append(("Page URL", True, self.page.url or "(unknown)"))

        try:
            day = await self.get_current_day()
            results.append(("Read day KPI", True, f"Day {day['current']} / {day['total']}"))
        except Exception as exc:
            results.append(("Read day KPI", False, str(exc)))

        try:
            locations = await self.get_owned_retail_locations()
            ok = bool(locations)
            detail = ", ".join(locations) if locations else "no retail locations found"
            results.append(("Retail panel", ok, detail))
        except Exception as exc:
            results.append(("Retail panel", False, str(exc)))

        return results
