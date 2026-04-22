import asyncio
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
import pandas as pd

# --- Global Configuration ---
CATEGORIES = ['news', 'metro-plus', 'video', 'sports', 'politics']
PAGES = 1

class Scrapper:
    def __init__(self):
        self.articles = []

    async def fetch_data(self, session, url):
        """Asynchronously fetches a URL using Browser Impersonation to bypass Cloudflare."""
        try:
            # impersonate="chrome" handles the headers and TLS fingerprint for you
            response = await session.get(url, impersonate="chrome", timeout=30)
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
            else:
                print(f"Cloudflare/Server Block: {url} (Status: {response.status_code})")
                return None
        except Exception as e:
            print(f"Network Error on {url}: {e}")
            return None

    def extract_article_list(self, soup):
        """
        Extracts metadata and identifies the category 
        by explicitly referring to the global CATEGORIES array.
        """
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

    async def _scrape_single_detail(self, session, article):
        """Worker function to scrape deep content for one article."""
        detail_soup = await self.fetch_data(session, article['link'])
        if detail_soup:
            # Author
            author_tag = detail_soup.find('span', class_='post-author')
            article['author'] = author_tag.text.strip().replace('By  ', '') if author_tag else 'N/A'
            
            # Content
            content_div = detail_soup.find('div', class_='post-content')
            article['content'] = content_div.text.strip().replace('\xa0', ' ') if content_div else ''

            # Image
            image_wrapper = detail_soup.find('div', class_='post-image-wrapper')
            if image_wrapper and image_wrapper.find('img'):
                article['image'] = image_wrapper.find('img')['src']
            else:
                article['image'] = ''

    async def fetch_all_details(self, session):
        """Runs all detail scraping tasks concurrently at full speed."""
        if not self.articles:
            print("No links collected yet.")
            return

        print(f"Scraping {len(self.articles)} article details through Cloudflare...")
        tasks = [self._scrape_single_detail(session, article) for article in self.articles]
        await asyncio.gather(*tasks)

    def save_results(self, filename='punch_results.csv'):
        """Method to save collected data to CSV."""
        if not self.articles:
            print("No data collected to save.")
            return
        
        df = pd.DataFrame(self.articles)
        df.to_csv(filename, index=False)
        print(f"\nSuccess! Data saved to {filename}")


async def main():
    scraper = Scrapper()

    # AsyncSession from curl_cffi handles connection pooling and browser impersonation
    async with AsyncSession() as session:
        
        for category in CATEGORIES:
            for page in range(1, PAGES + 1):
                url = f'https://punchng.com/topics/{category}/page/{page}/'
                print(f"Fetching List: {url}")
                soup = await scraper.fetch_data(session, url)
                scraper.extract_article_list(soup)

        await scraper.fetch_all_details(session)

    scraper.save_results('punch_cloudflare_clean.csv')

if __name__ == "__main__":
    asyncio.run(main())
