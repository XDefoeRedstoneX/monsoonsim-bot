import asyncio
from pyppeteer import connect


async def main():
    """
    Connects to an already-running Chrome instance and finds the MonsoonSim page.
    """
    print("Attempting to connect to Chrome on port 9222...")

    try:
        # The browserURL is the endpoint created by the --remote-debugging-port flag.
        browser = await connect(browserURL="http://127.0.0.1:9222")
        print("Successfully connected to the browser!")

        # Get a list of all open tabs (pages)
        pages = await browser.pages()

        target_page = None
        target_url_fragment = ["sim133.monsoonsim.com","sim56.monsoonsim.com"]

        # Loop through all open pages to find our target
        # This is the Python equivalent of your AHK's Chrome.GetPageByURL() [cite: 2, 13]
        for p in pages:
            for url_fragment in target_url_fragment:
                if url_fragment in p.url:
                    target_page = p
                    break

        if target_page:
            print(f"Found MonsoonSIM page: {target_page.url}")
            # Bring the page to the front to make sure it's active

            # --- From here, you can add your automation logic ---
            # For example, let's get the title of the page
            title = await target_page.title()
            print(f"The page title is: '{title}'")

        else:
            print(f"Could not find a page with the URL fragment: {target_url_fragment}")

        await browser.disconnect()
        print("Disconnected from browser. The window will remain open.")

    except Exception as e:
        print(f"Connection failed. Is Chrome running with --remote-debugging-port=9222?")
        print(f"Error: {e}")


if __name__ == '__main__':
    asyncio.run(main())
