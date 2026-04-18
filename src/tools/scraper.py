from playwright.async_api import async_playwright

try:
    from google.adk import Tool
except ImportError:
    class Tool:
        pass

from src.observability.metrics import tool_timer

class ScraperTool(Tool):
    def __init__(self, allowlist=None):
        self.allowlist = allowlist or []

    @tool_timer("ScraperTool")
    async def scrape(self, url):
        if self.allowlist and not any(domain in url for domain in self.allowlist):
            return f"Error: Domain {url} not in allowlist"
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                content = await page.content()
                await browser.close()
                return content
        except Exception as e:
            return f"Error scraping {url}: {str(e)}"
