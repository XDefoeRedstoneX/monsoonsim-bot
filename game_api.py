# game_api.py
# Your reusable library for all low-level game interactions.
import asyncio
import math
import re

# --- Data Constants for Different Product Sets ---
JUICE_SET = {
    "code_map": {"Apple Juice": "P1", "Orange Juice": "P2", "Melon Juice": "P3"},
    "space_usage": {"Apple Juice": 0.0033, "Orange Juice": 0.0033, "Melon Juice": 0.0033},
    "valid_order_quantities": [1000, 3000, 5000, 8000, 12000, 20000, 30000, 40000, 50000, 60000, 80000, 100000, 120000]
}

MASK_SET = {
    "code_map": {"Dust Mask": "P1", "Surgical Mask": "P2", "KN95": "P3"},
    "space_usage": {"Dust Mask": 0.0133, "Surgical Mask": 0.0083, "KN95": 0.012},
    "valid_order_quantities": [1000, 3000, 5000, 8000, 12000, 20000, 30000, 40000, 50000, 60000, 80000, 100000, 120000]
}

CAR_SET = {
    "code_map": {"Sedan": "P1", "SUV": "P2", "Truck": "P3"},
    "space_usage": {"Sedan": 18.5, "SUV": 23.2, "Truck": 28},
    "valid_order_quantities": [1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50]
}

COFFEE_SET = {
    "code_map": {"Americano": "P1", "Hot Chocolate": "P2", "Bubble Milk Tea": "P3"},
    "space_usage": {"Americano": 0.005, "Hot Chocolate": 0.005, "Bubble Milk Tea": 0.005},
    "valid_order_quantities": [1000, 3000, 5000, 8000, 12000, 20000, 30000, 40000, 50000, 60000, 80000, 100000, 120000]
}

ELECTRONICS_SET = {
    "code_map": {"Laptop": "P1", "Smartphone": "P2", "Witchtendo Switch": "P3"},
    "space_usage": {"Laptop": 0.31, "Smartphone": 0.012, "Witchtendo Switch": 0.024},
    "valid_order_quantities": [100, 300, 500, 800, 1200, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000]
}

# --- Global State Variables (Product) ---
PRODUCT_CODE_MAP = JUICE_SET["code_map"]
PRODUCT_SPACE_USAGE = JUICE_SET["space_usage"]
ALL_PRODUCTS = list(PRODUCT_CODE_MAP.keys())
VALID_ORDER_QUANTITIES = JUICE_SET["valid_order_quantities"]

# --- Hard-coded Location Maps ---
INDONESIA_LOCATION_ID_MAP = {
    "Balikpapan": "11", "Jakarta": "12", "Denpasar": "13", "Medan": "14",
    "Palembang": "15", "Makassar": "16", "Surabaya": "17"
}

CHINA_LOCATION_ID_MAP = {
    "Guangzhou": "11", "Beijing": "12", "Chengdu": "13", "Wuhan": "14",
    "Zhuhai": "15", "Dongguan": "16", "Shanghai": "17"
}

# --- Global State Variables (Location) ---
LOCATION_ID_MAP = INDONESIA_LOCATION_ID_MAP  # Default to Indonesia
CURRENT_LOCATION_SET = "Indonesia"  # Keep track of the name
_alternating_buy_counter = 0


# --- Function to Switch Product Sets ---
def set_active_product_set(set_name):
    """Switches the global constants to use the specified product set."""
    global PRODUCT_CODE_MAP, PRODUCT_SPACE_USAGE, ALL_PRODUCTS, VALID_ORDER_QUANTITIES

    if set_name == "Juice":
        active_set = JUICE_SET
    elif set_name == "Mask":
        active_set = MASK_SET
    elif set_name == "Car":
        active_set = CAR_SET
    elif set_name == "Coffee":
        active_set = COFFEE_SET
    elif set_name == "Electronics":
        active_set = ELECTRONICS_SET
    else:
        raise ValueError(f"Unknown product set: {set_name}")

    PRODUCT_CODE_MAP = active_set["code_map"]
    PRODUCT_SPACE_USAGE = active_set["space_usage"]
    ALL_PRODUCTS = list(PRODUCT_CODE_MAP.keys())
    VALID_ORDER_QUANTITIES = active_set["valid_order_quantities"]
    print(f"Product set switched to: {set_name}")
    return ALL_PRODUCTS


# --- Function to Switch Location Sets ---
def set_active_location_set(set_name):
    """Switches the global LOCATION_ID_MAP to the specified set."""
    global LOCATION_ID_MAP, CURRENT_LOCATION_SET

    if set_name == "Indonesia":
        LOCATION_ID_MAP = INDONESIA_LOCATION_ID_MAP
    elif set_name == "China":
        LOCATION_ID_MAP = CHINA_LOCATION_ID_MAP
    else:
        raise ValueError(f"Unknown location set: {set_name}")

    CURRENT_LOCATION_SET = set_name
    print(f"Location set switched to: {set_name}")
    return True


# --- Core Interaction Primitives ---
async def find_element(page, selector, selector_type='css', timeout=5000):
    """Finds a single element and returns its handle, waiting for it to appear first."""
    try:
        if selector_type == 'css':
            await page.waitForSelector(selector, timeout=timeout)
            return await page.querySelector(selector)
        elif selector_type == 'xpath':
            await page.waitForXPath(selector, timeout=timeout)
            handles = await page.xpath(selector)
            return handles[0] if handles else None
        raise ValueError("selector_type must be 'css' or 'xpath'")
    except Exception as e:
        raise Exception(f"Could not find element with {selector_type} selector '{selector}': {e}")


async def click_element(page, selector, selector_type='css'):
    """Finds an element and performs a standard (simulated) click."""
    element = await find_element(page, selector, selector_type)
    if not element: raise Exception(f"Element handle not found for click: {selector}")
    await element.click()


async def js_click_element(page, selector, selector_type='css'):
    """Finds an element and triggers a click programmatically using JavaScript."""
    print(f"Attempting programmatic JS click on: {selector}")
    try:
        if selector_type == 'css':
            await page.waitForSelector(selector, timeout=5000)
            await page.evaluate(f'document.querySelector("{selector}").click()')
        elif selector_type == 'xpath':
            await page.waitForXPath(selector, timeout=5000)
            await page.evaluate(
                f'document.evaluate("{selector}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click()')
        else:
            raise ValueError("selector_type must be 'css' or 'xpath'")
    except Exception as e:
        raise Exception(f"Failed programmatic JS click on {selector_type} selector '{selector}': {e}")


# --- NEW: Rate Limit Helper ---
async def _check_for_rate_limit(page):
    """Checks for the 'Slow down' message and returns True if found."""
    try:
        content = await page.evaluate("document.body.textContent")
        if "Slow down, you click too fast" in content:
            return True
    except Exception:
        pass  # Page might be navigating, etc.
    return False


# --- Automation Core Functions ---
async def get_current_day(page):
    """Reads the current day from the top bar."""
    try:
        day_text = await page.evaluate("document.querySelector('#KPI_DAY____').textContent")
        current_day, total_days = map(int, day_text.split(' / '))
        return {"current": current_day, "total": total_days}
    except Exception as e:
        raise Exception(f"Could not parse current day: {e}")


async def wait_for_next_day(page, current_day_num):
    """Intelligently waits for the day counter to change."""
    print(f"Waiting for day to advance past {current_day_num}...")
    for _ in range(45):  # Timeout after ~45 seconds
        day_info = await get_current_day(page)
        if day_info["current"] > current_day_num:
            print(f"New day detected: {day_info['current']}")
            return day_info
        await asyncio.sleep(1)
    raise Exception("Timeout: Day did not advance.")


# --- Service / HR Module ---
async def handle_service_requests(page):
    """MODIFIED: Navigates to Service and handles the first available request, with retries."""

    for attempt in range(3):  # Try up to 3 times
        try:
            print("Checking for service requests...")
            try:
                await click_element(page, '#boxmodsrv')
                await click_element(page, '#MENU2_SRVincm')
                await asyncio.sleep(1)
            except:
                return "Service module not found or enabled. Skipping."

            try:
                request_link = await find_element(page, "a[href*='cmd=SRV_INCOMING']", 'css', timeout=2000)
                await request_link.click()
                await page.waitForSelector('#facebox #submit_button', {'visible': True})
                print("Opened service request. Analyzing mandays...")
            except:
                return "No new service requests found."

            force_open_tab_js = """
            function forceOpenTab(tabName) {
                let tabs = document.querySelectorAll(".ui-tabs-tab");
                tabs.forEach(tab => tab.classList.remove('ui-tabs-active', 'ui-state-active'));
                let selectedTab = [...tabs].find(tab => tab.textContent.includes(tabName));
                if (selectedTab) {
                    selectedTab.classList.add('ui-tabs-active', 'ui-state-active');
                    let panelId = selectedTab.querySelector("a").getAttribute("href");
                    document.querySelectorAll(".ui-tabs-panel").forEach(p => p.style.display = 'none');
                    document.querySelector(panelId).style.display = 'block';
                }
            }"""
            await page.evaluate(force_open_tab_js)

            click_buttons_js = """
            function clickButtonsForTab(tabName, requiredClicks) {
                forceOpenTab(tabName); 
                return new Promise(resolve => setTimeout(() => {
                    let tabId = jQuery('.ui-tabs-tab').filter(function() { return jQuery(this).text().trim() === tabName; }).attr('aria-controls');
                    if (!tabId) return resolve();
                    let buttons = jQuery('#' + tabId).find('.circle.thecb').not('.disabled').slice(0, requiredClicks);
                    buttons.each(function() { jQuery(this).trigger('click'); });
                    resolve();
                }, 300));
            }"""
            await page.evaluate(click_buttons_js)

            mandays = await page.evaluate('''
                () => {
                    const elements = document.querySelectorAll('.col-md-5');
                    const mandays = [];
                    elements.forEach(element => {
                        const match = element.textContent.match(/Required Mandays\\s*:\\s*(\\d+)/);
                        if (match) mandays.push(parseInt(match[1]));
                    });
                    return mandays;
                }
            ''')

            if mandays:
                if mandays[0] > 0: await page.evaluate(
                    f"clickButtonsForTab('Marketing Srv', {mandays[0]})"); await asyncio.sleep(0.3)
                if len(mandays) > 1 and mandays[1] > 0: await page.evaluate(
                    f"clickButtonsForTab('Franchise Srv', {mandays[1]})"); await asyncio.sleep(0.3)
                if len(mandays) > 2 and mandays[2] > 0: await page.evaluate(
                    f"clickButtonsForTab('Technical Srv', {mandays[2]})")
                print(f"Assigned staff for mandays: {mandays}")

            await asyncio.sleep(0.5)
            await click_element(page, '#facebox #submit_button')
            await page.waitForSelector('#facebox', {'hidden': True})

            return "Service request handled successfully."  # Success, break the retry loop

        except Exception as e:
            print(f"Service request attempt {attempt + 1} failed: {e}")
            if await _check_for_rate_limit(page):
                print("Rate limit detected. Waiting 1.5s and retrying...")
                await asyncio.sleep(1.5)
                continue  # Go to the next attempt
            else:
                return f"Service request failed: {e}"  # Real error, don't retry

    return "Service request failed after 3 attempts."


# --- Retail Module ---
async def get_retail_space_info(page, location_name):
    """Reads the space utilization from the Retail KPI panel."""
    print(f"Reading space info for {location_name}...")
    try:
        space_info_xpath = f"//div[@id='RTL']//div[contains(., '{location_name}')]/following-sibling::li[contains(., 'Space utilization')]//div"
        space_element = await find_element(page, space_info_xpath, 'xpath')
        full_text = await page.evaluate('(element) => element.textContent', space_element)
        match = re.search(r'([\d,]+)\s*/\s*([\d,]+)', full_text)
        if not match: raise Exception(f"Could not parse space usage from: '{full_text}'")
        used_m2 = int(match.group(1).replace(',', ''))
        total_m2 = int(match.group(2).replace(',', ''))
        return {'used_m2': used_m2, 'total_m2': total_m2}
    except Exception as e:
        raise Exception(f"Could not read space info for '{location_name}': {e}")


async def get_owned_retail_locations(page):
    """Scrapes the Retail KPI panel for owned retail location names."""
    print("Scraping for owned retail locations...")
    try:
        return await page.evaluate('''
            () => Array.from(document.querySelectorAll("#RTL .kpi_title"))
                        .map(el => el.textContent.replace("Retail", "").replace(/\u00A0/g, ' ').trim())
        ''')
    except Exception as e:
        raise Exception(f"Could not scrape owned retail locations: {e}")


async def get_all_retail_stock(page, location_name):
    """Reads the current stock levels for all products in a specific retail location."""
    print(f"Reading all stock levels for {location_name}...")
    stock = {}
    try:
        location_kpi_xpath = f"//div[@id='RTL']//div[contains(@class, 'kpi_title') and contains(., '{location_name}')]"
        for product_name in ALL_PRODUCTS:
            stock_xpath = f"{location_kpi_xpath}/following-sibling::li[contains(., '{product_name}')]/span[@class='right']"
            stock_element = await find_element(page, stock_xpath, 'xpath')
            stock_text = await page.evaluate('(element) => element.textContent', stock_element)
            stock[product_name] = int(stock_text.replace(',', ''))
        print(f"Current stock: {stock}")
        return stock
    except Exception as e:
        raise Exception(f"Could not read all stock for '{location_name}': {e}")


def _calculate_best_fit_quantity(available_space, space_per_unit):
    """Calculates the largest valid order size that fits in the available space."""
    if available_space <= 0 or space_per_unit <= 0: return 0
    max_units_possible = math.floor(available_space / space_per_unit)
    if max_units_possible == 0: return 0
    for qty in sorted(VALID_ORDER_QUANTITIES, reverse=True):
        if qty <= max_units_possible: return qty
    return 0


async def _calculate_order_logic(page, location_name, prioritized_products, target_fill_percentage):
    """
    Internal function that performs all the calculation logic for replenishment.
    This is shared by both the "dry run" calculator and the real procurement function.
    Returns a dictionary of orders to place, e.g. {"Apple Juice": 12000, "Melon Juice": 8000}
    """
    print(
        f"Calculating replenishment for '{location_name}' to {target_fill_percentage}%. Prioritizing: {prioritized_products or 'None'}")

    # 1. Gather all required data
    space_info = await get_retail_space_info(page, location_name)
    current_used_m2 = space_info['used_m2']
    total_m2 = space_info['total_m2']
    current_stock = await get_all_retail_stock(page, location_name)

    # 2. Calculate target space and individual product quotas
    target_space_to_use = total_m2 * (target_fill_percentage / 100.0)
    product_quotas = {}

    if prioritized_products:
        non_prioritized_products = [p for p in ALL_PRODUCTS if p not in prioritized_products]
        prio_quota = (target_space_to_use * 0.60) / len(prioritized_products) if prioritized_products else 0
        non_prio_quota = (target_space_to_use * 0.40) / len(
            non_prioritized_products) if non_prioritized_products else 0
        for p in prioritized_products: product_quotas[p] = prio_quota
        for p in non_prioritized_products: product_quotas[p] = non_prio_quota
    else:
        quota_per_product = target_space_to_use / len(ALL_PRODUCTS)
        for p in ALL_PRODUCTS: product_quotas[p] = quota_per_product

    # 3. Calculate orders for each product independently
    orders_to_place = {}
    for product in ALL_PRODUCTS:
        quota = product_quotas.get(product, 0)
        current_space = current_stock.get(product, 0) * PRODUCT_SPACE_USAGE.get(product, 0.01)
        space_to_fill = quota - current_space
        if space_to_fill > 0:
            qty = _calculate_best_fit_quantity(space_to_fill, PRODUCT_SPACE_USAGE[product])
            if qty > 0:
                orders_to_place[product] = qty
                print(f"Rule: '{product}' needs to fill {space_to_fill:.2f}m². Ordering {qty}.")

    # 4. Final Safety Check against physical remaining space
    planned_order_space = sum(q * PRODUCT_SPACE_USAGE.get(p, 0) for p, q in orders_to_place.items())
    physical_remaining_space = total_m2 - current_used_m2

    if planned_order_space > physical_remaining_space:
        print("WARNING: Target fill exceeds physical space. Scaling back orders...")
        scaled_orders = {}
        temp_remaining_space = physical_remaining_space
        sorted_orders = sorted(orders_to_place.items(), key=lambda i: i[1] * PRODUCT_SPACE_USAGE[i[0]],
                               reverse=True)
        for product, qty in sorted_orders:
            new_qty = _calculate_best_fit_quantity(temp_remaining_space, PRODUCT_SPACE_USAGE[product])
            if new_qty > 0:
                scaled_orders[product] = new_qty
                temp_remaining_space -= new_qty * PRODUCT_SPACE_USAGE[product]
        orders_to_place = scaled_orders

    return orders_to_place


async def calculate_replenish_order(page, location_name, prioritized_products, target_fill_percentage=100):
    """
    Public function for the GUI to call.
    Performs a "dry run" calculation without clicking any buy buttons.
    Returns the dictionary of orders.
    """
    try:
        orders = await _calculate_order_logic(page, location_name, prioritized_products, target_fill_percentage)
        return orders
    except Exception as e:
        print(f"Error during calculation for {location_name}: {e}")
        raise Exception(f"Calculation failed for {location_name}: {e}")  # Re-raise to be caught by GUI


async def procure_for_retail_location(page, location_name, prioritized_products, target_fill_percentage=100,
                                      vendor_name="VFG2"):
    """
    MODIFIED: Handles replenishment with retries for rate limiting.
    """
    for attempt in range(3):  # Try up to 3 times
        try:
            # 1-4. Calculate the order
            orders_to_place = await _calculate_order_logic(page, location_name, prioritized_products,
                                                           target_fill_percentage)

            if not orders_to_place:
                return "Analysis complete. No order needed to meet targets."

            # 5. Execute the order
            print(f"Executing order for {location_name}: {orders_to_place}")
            await click_element(page, '#boxmodrtl')
            await click_element(page, '#MENU2_retail_vendor')
            vendor_xpath = f"//div[contains(@class, 'vendor-box') and .//div[contains(text(), '{vendor_name}')]]//a[contains(@href, 'BUY_FG')]"
            await js_click_element(page, vendor_xpath, 'xpath')
            await page.waitForSelector('#facebox #submit_button', {'visible': True})

            location_id = LOCATION_ID_MAP.get(location_name)
            if not location_id:
                raise Exception(
                    f"Location '{location_name}' not found in the '{CURRENT_LOCATION_SET}' map. Check Global Settings.")

            await page.select('#destination_rtl', location_id)
            for product_name, quantity in orders_to_place.items():
                product_code = PRODUCT_CODE_MAP.get(product_name)
                if not product_code: continue
                await page.select(f'#facebox #{product_code}', str(quantity))
            await click_element(page, '#facebox #submit_button')
            await page.waitForSelector('#facebox', {'hidden': True})
            order_summary = ", ".join([f"{qty} of {prod}" for prod, qty in orders_to_place.items()])

            return f"Successfully ordered: {order_summary} for {location_name}."  # Success, break retry loop

        except Exception as e:
            print(f"Procurement attempt {attempt + 1} failed: {e}")
            if await _check_for_rate_limit(page):
                print("Rate limit detected. Waiting 1.5s and retrying...")
                await asyncio.sleep(1.5)
                continue  # Go to the next attempt
            else:
                return f"SKIPPED {location_name}: Could not process replenishment. Reason: {e}"  # Real error

    return f"SKIPPED {location_name}: Failed to process replenishment after 3 attempts."

