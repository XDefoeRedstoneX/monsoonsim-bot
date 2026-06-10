"""Centralised DOM selectors for the MonsoonSim UI.

When the game's front-end changes, this is the *only* file that should need
updating. CSS selectors are plain strings; XPath selectors are prefixed with
``xpath=`` so they can be passed straight to Playwright's query helpers.
"""

# --- Top bar / KPIs ---
KPI_DAY = "#KPI_DAY____"

# --- Service / HR module ---
SERVICE_MODULE_BOX = "#boxmodsrv"
SERVICE_INCOMING_MENU = "#MENU2_SRVincm"
SERVICE_REQUEST_LINK = "a[href*='cmd=SRV_INCOMING']"

# --- Retail module ---
RETAIL_MODULE_BOX = "#boxmodrtl"
RETAIL_VENDOR_MENU = "#MENU2_retail_vendor"
RETAIL_DESTINATION_SELECT = "#destination_rtl"

# --- Shared dialog (facebox) ---
FACEBOX = "#facebox"
FACEBOX_SUBMIT = "#facebox #submit_button"

# --- Retail KPI panel (XPath, because they depend on text content) ---
RETAIL_KPI_TITLES = "#RTL .kpi_title"


def retail_space_xpath(location_name: str) -> str:
    return (
        f"xpath=//div[@id='RTL']//div[contains(., '{location_name}')]"
        f"/following-sibling::li[contains(., 'Space utilization')]//div"
    )


def retail_stock_xpath(location_name: str, product_name: str) -> str:
    return (
        f"xpath=//div[@id='RTL']//div[contains(@class, 'kpi_title') and contains(., '{location_name}')]"
        f"/following-sibling::li[contains(., '{product_name}')]/span[@class='right']"
    )


def vendor_buy_xpath(vendor_name: str) -> str:
    return (
        f"xpath=//div[contains(@class, 'vendor-box') and "
        f".//div[contains(text(), '{vendor_name}')]]//a[contains(@href, 'BUY_FG')]"
    )


def product_qty_select(product_code: str) -> str:
    return f"#facebox #{product_code}"
