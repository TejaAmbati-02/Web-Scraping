import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd

CATEGORIES = ['news', 'metro-plus', 'video', 'sports', 'politics']
PAGES = 1

class Scrapper:
    def __init__(self):
        self.articles = []

    async def fetch_data(self, browser_context, url):
        """Uses a real browser page to bypass Cloudflare 403 blocks."""
        page = await browser_context.new_page()
        try:
            # Navigate to the URL and wait for the content to load
            print(f"Opening: {url}")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            if response.status == 200:
                content = await page.content()
                return BeautifulSoup(content, 'html.parser')
            else:
                print(f"Blocked by Cloudflare! Status: {response.status}")
                return None
        except Exception as e:
            print(f"Error loading {url}: {e}")
            return None
        finally:
            await page.close()

    def extract_article_list(self, soup):
        """Identifies category by referring to global CATEGORIES."""
        if not soup:
            return

        page_title_tag = soup.find('h1', class_='page-title')
        page_title = page_title_tag.text.lower() if page_title_tag else ""
        
        current_cat_label = "General"
        for cat in CATEGORIES:
            if cat in page_title or cat.replace('-', ' ') in page_title:
                current_cat_label = cat
                break

        article_container = soup.find('div', class_='latest-news-timeline-section')
        if not article_container:
            return

        article_temp = article_container.find_all('article')
        for article in article_temp:
            try:
                title = article.find('h1', 'post-title').text.strip().replace('\xa0', ' ')
                excerpt = article.find('p', 'post-excerpt').text.strip().replace('\xa0', ' ')
                date = article.find('span', 'post-date').text.strip()
                link = article.find('a')['href']

                self.articles.append({
                    'category': current_cat_label,
                    'title': title,
                    'excerpt': excerpt,
                    'date': date,
                    'link': link
                })
            except (AttributeError, TypeError):
                continue

    async def _scrape_single_detail(self, browser_context, article):
        """Worker to scrape content for one article using a real browser page."""
        detail_soup = await self.fetch_data(browser_context, article['link'])
        if detail_soup:
            author_tag = detail_soup.find('span', class_='post-author')
            article['author'] = author_tag.text.strip().replace('By  ', '') if author_tag else 'N/A'
            
            content_div = detail_soup.find('div', class_='post-content')
            article['content'] = content_div.text.strip().replace('\xa0', ' ') if content_div else ''

            image_wrapper = detail_soup.find('div', class_='post-image-wrapper')
            if image_wrapper and image_wrapper.find('img'):
                article['image'] = image_wrapper.find('img')['src']
            else:
                article['image'] = ''

    async def fetch_all_details(self, browser_context):
        """Runs all detail scraping tasks concurrently."""
        if not self.articles:
            return

        print(f"\nScraping {len(self.articles)} details at high speed...")
        tasks = [self._scrape_single_detail(browser_context, article) for article in self.articles]
        await asyncio.gather(*tasks)

    def save_results(self, filename='punch_data.csv'):
        """Saves results to CSV."""
        if self.articles:
            df = pd.DataFrame(self.articles)
            df.to_csv(filename, index=False)
            print(f"\nDone! Saved to {filename}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        # Create a context that mimics a real Chrome browser
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        
        scraper = Scrapper()

        for category in CATEGORIES:
            for page in range(1, PAGES + 1):
                url = f'https://punchng.com/topics/{category}/page/{page}/'
                soup = await scraper.fetch_data(context, url)
                scraper.extract_article_list(soup)

        # 2. Collect Details
        await scraper.fetch_all_details(context)

        await browser.close()
        scraper.save_results('punch_final.csv')

if __name__ == "__main__":
    asyncio.run(main())
