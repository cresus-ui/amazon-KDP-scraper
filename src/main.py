"""Amazon KDP Book Scraper - Extract comprehensive book data from Amazon KDP.

This Actor scrapes book information including titles, authors, prices, ratings,
reviews, and metadata from Amazon's Kindle Direct Publishing platform.
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from apify import Actor
from bs4 import BeautifulSoup
import httpx
from httpx import AsyncClient, Response


class AmazonKDPScraper:
    """Amazon KDP Book Scraper class."""
    
    def __init__(self, client: AsyncClient, config: Dict[str, Any]):
        self.client = client
        self.config = config
        self.base_url = "https://www.amazon.com"
        self.request_delay = config.get('requestDelay', 2)
        self._last_error_code = None
        self._session_cookies = {}
        self._consecutive_failures = 0
        self._last_success_time = None
        
        # Enhanced User-Agent pool with more recent and diverse options
        self.user_agents = [
            # Chrome on Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
            
            # Chrome on macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            
            # Firefox on Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
            
            # Firefox on macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0',
            
            # Safari on macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
            
            # Edge on Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.0.0'
        ]
        
    async def _warm_up_session(self) -> bool:
        """Warm up the session by visiting Amazon homepage to establish realistic browsing pattern."""
        try:
            Actor.log.info('Warming up session by visiting Amazon homepage')
            homepage_response = await self._make_request('https://www.amazon.com', skip_warmup=True)
            
            if homepage_response and homepage_response.status_code == 200:
                # Simulate reading the homepage
                await asyncio.sleep(random.uniform(2, 5))
                
                # Sometimes visit the books section
                if random.random() < 0.7:
                    books_url = 'https://www.amazon.com/books-used-books-textbooks/b?ie=UTF8&node=283155'
                    books_response = await self._make_request(books_url, skip_warmup=True)
                    if books_response and books_response.status_code == 200:
                        await asyncio.sleep(random.uniform(1, 3))
                        Actor.log.info('Successfully warmed up session with books section visit')
                    else:
                        Actor.log.warning('Failed to visit books section during warm-up')
                
                return True
            else:
                Actor.log.warning('Failed to warm up session - homepage request failed')
                return False
                
        except Exception as e:
            Actor.log.error(f'Session warm-up failed: {str(e)}')
            return False
    
    async def _reset_session_strategy(self) -> None:
        """Reset session with new identity to avoid detection patterns."""
        try:
            Actor.log.info('Resetting session strategy...')
            
            # Clear session cookies
            self._session_cookies = {}
            
            # Reset error tracking
            self._last_error_code = None
            
            # Close and recreate HTTP client with new configuration
            if hasattr(self, 'client') and self.client:
                await self.client.aclose()
            
            # Recreate client with fresh session
            await self._setup_http_client()
            
            # Skip warm-up during session reset to avoid recursion
            Actor.log.info('Session reset completed - skipping warm-up to avoid recursion')
            
            Actor.log.info('Session strategy reset completed')
            
        except Exception as e:
            Actor.log.error(f'Failed to reset session strategy: {str(e)}')
    
    async def _intelligent_backoff(self, consecutive_failures: int) -> None:
        """Implement intelligent backoff strategy based on failure patterns."""
        if consecutive_failures <= 2:
            # Light failures - short delays
            delay = random.uniform(5, 15)
        elif consecutive_failures <= 5:
            # Moderate failures - medium delays with session reset
            delay = random.uniform(30, 90)
            if consecutive_failures == 3:
                await self._reset_session_strategy()
        else:
            # Heavy failures - long delays with complete strategy change
            delay = random.uniform(300, 600)
            await self._reset_session_strategy()
        
        Actor.log.info(f'Intelligent backoff: {delay:.1f}s after {consecutive_failures} consecutive failures')
        await asyncio.sleep(delay)
    
    async def search_books(self, search_term: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for books on Amazon using the given search term."""
        # Warm up session before starting search (human-like behavior)
        if not hasattr(self, '_session_warmed'):
            await self._warm_up_session()
            self._session_warmed = True
        
        search_url = self._build_search_url(search_term, category)
        Actor.log.info(f'Searching for books: {search_term} in category: {category}')
        
        response = await self._make_request(search_url)
        if not response:
            return []
            
        soup = BeautifulSoup(response.content, 'lxml')
        book_links = self._extract_book_links(soup)
        
        books = []
        max_results = self.config.get('maxResults', 100)
        
        for i, book_url in enumerate(book_links[:max_results]):
            if i > 0:
                await asyncio.sleep(self.request_delay)
                
            book_data = await self._scrape_book_details(book_url)
            if book_data and self._meets_criteria(book_data):
                books.append(book_data)
                Actor.log.info(f'Scraped book: {book_data.get("title", "Unknown")}')
                
        return books
    
    def _build_search_url(self, search_term: str, category: Optional[str] = None) -> str:
        """Build Amazon search URL with proper parameters."""
        params = {
            'k': search_term,
            'i': 'digital-text',  # Kindle books
            'ref': 'sr_nr_i_0'
        }
        
        # Add sorting parameter
        sort_by = self.config.get('sortBy', 'relevance')
        if sort_by != 'relevance':
            sort_mapping = {
                'price-low-to-high': 'price-asc-rank',
                'price-high-to-low': 'price-desc-rank',
                'avg-customer-review': 'review-rank',
                'newest-arrivals': 'date-desc-rank'
            }
            params['s'] = sort_mapping.get(sort_by, 'relevance')
            
        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}/s?{query_string}"
    
    async def _setup_http_client(self) -> None:
        """Setup HTTP client with appropriate configuration."""
        # This method will be called from main() where proxy configuration is available
        pass
    
    async def _make_request(self, url: str, max_retries: int = 3, skip_warmup: bool = False) -> Optional[Response]:
        """Make HTTP request with advanced retry logic and anti-detection measures."""
        base_delay = 2.0
        captcha_attempts = 0
        
        for attempt in range(max_retries):
            try:
                # Enhanced headers with more realistic browser simulation
                headers = self._get_realistic_headers(url)
                
                # Progressive delay with jitter for retry attempts
                if attempt > 0:
                    await self._adaptive_delay_strategy(attempt, self._last_error_code)
                
                # Enhanced delay with human-like patterns
                request_delay = self.config.get('requestDelay', 2)
                # Add variability to mimic human browsing patterns
                human_delay = random.uniform(request_delay * 0.8, request_delay * 2.0)
                # Occasionally add longer pauses (like humans reading)
                if random.random() < 0.1:  # 10% chance of longer pause
                    human_delay += random.uniform(5, 15)
                
                await asyncio.sleep(human_delay)
                
                response = await self.client.get(url, headers=headers, follow_redirects=True)
                
                # Store last error code for adaptive delays
                self._last_error_code = response.status_code
                
                # Enhanced CAPTCHA detection
                if self._is_captcha_page(response):
                    captcha_attempts += 1
                    should_continue = await self._handle_captcha_scenario(response, captcha_attempts - 1)
                    
                    if should_continue and attempt < max_retries - 1:
                        # Reset session cookies and change behavior after CAPTCHA
                        self._session_cookies = {}
                        self._consecutive_failures += 1
                        continue
                    else:
                        Actor.log.error('Max CAPTCHA attempts reached or retry limit exceeded')
                        self._consecutive_failures += 1
                        return None
                
                # Enhanced status code handling with specific strategies
                if response.status_code == 200:
                    # Reset error tracking on success
                    self._last_error_code = None
                    self._consecutive_failures = 0
                    self._last_success_time = datetime.now()
                    # Store successful session cookies
                    if response.cookies:
                        self._session_cookies.update(dict(response.cookies))
                    return response
                    
                elif response.status_code == 503:
                    self._consecutive_failures += 1
                    Actor.log.warning(f'Service unavailable (503) on attempt {attempt + 1} - Server overloaded')
                    # Use adaptive delay strategy
                    if attempt < max_retries - 1:
                        await self._adaptive_delay_strategy(attempt, 503)
                        # Apply intelligent backoff for repeated 503s
                        if self._consecutive_failures >= 3:
                            await self._intelligent_backoff(self._consecutive_failures)
                    continue
                    
                elif response.status_code == 429:
                    self._consecutive_failures += 1
                    Actor.log.warning(f'Rate limited (429) on attempt {attempt + 1}')
                    # Extract retry-after header if available
                    retry_after = response.headers.get('Retry-After')
                    if retry_after and retry_after.isdigit():
                        delay = int(retry_after) + random.uniform(5, 15)
                        Actor.log.info(f'Respecting Retry-After header: {delay}s')
                        await asyncio.sleep(delay)
                    else:
                        await self._adaptive_delay_strategy(attempt, 429)
                    continue
                    
                elif response.status_code == 403:
                    self._consecutive_failures += 1
                    Actor.log.warning(f'Forbidden (403) on attempt {attempt + 1} - Possible IP block')
                    
                    # Check if this is a CAPTCHA-related 403
                    if self._is_captcha_page(response):
                        captcha_attempts += 1
                        should_continue = await self._handle_captcha_scenario(response, captcha_attempts - 1)
                        
                        if should_continue and attempt < max_retries - 1:
                            self._session_cookies = {}
                            continue
                        else:
                            return None
                    
                    # Use adaptive delay for regular 403 errors
                    if attempt < max_retries - 1:
                        await self._adaptive_delay_strategy(attempt, 403)
                        # Apply intelligent backoff for repeated 403s (possible IP blocks)
                        if self._consecutive_failures >= 2:
                            await self._intelligent_backoff(self._consecutive_failures)
                    continue
                    
                elif response.status_code == 404:
                    Actor.log.error(f'Page not found (404): {url}')
                    return None
                    
                else:
                    self._consecutive_failures += 1
                    Actor.log.warning(f'Unexpected status code {response.status_code} on attempt {attempt + 1}')
                    if attempt < max_retries - 1:
                        await self._adaptive_delay_strategy(attempt)
                    continue
                    
            except Exception as e:
                Actor.log.error(f'Request failed on attempt {attempt + 1}: {str(e)}')
                self._consecutive_failures += 1
                if attempt < max_retries - 1:
                    # Use adaptive delay for exceptions too
                    await self._adaptive_delay_strategy(attempt)
                    # Apply intelligent backoff for repeated connection failures
                    if self._consecutive_failures >= 3:
                        await self._intelligent_backoff(self._consecutive_failures)
                    continue
                else:
                    return None
                    
        # All attempts failed - apply final intelligent backoff
        self._consecutive_failures += 1
        Actor.log.error(f'All {max_retries} attempts failed for {url} (consecutive failures: {self._consecutive_failures})')
        
        # If we have many consecutive failures, apply intelligent backoff before returning
        if self._consecutive_failures >= 5:
            await self._intelligent_backoff(self._consecutive_failures)
        
        return None
    
    def _extract_book_links(self, soup: BeautifulSoup) -> List[str]:
        """Extract book detail page links from search results."""
        links = []
        
        # Find book containers in search results
        book_containers = soup.find_all('div', {'data-component-type': 's-search-result'})
        
        for container in book_containers:
            link_element = container.find('h2', class_='a-size-mini')
            if link_element:
                link = link_element.find('a')
                if link and link.get('href'):
                    full_url = self.base_url + link['href']
                    links.append(full_url)
                    
        return links
    
    async def _scrape_book_details(self, book_url: str) -> Optional[Dict[str, Any]]:
        """Scrape detailed information from a book's detail page."""
        response = await self._make_request(book_url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Extract ASIN from URL
        asin_match = re.search(r'/dp/([A-Z0-9]{10})', book_url)
        asin = asin_match.group(1) if asin_match else None
        
        book_data = {
            'type': 'book',
            'url': book_url,
            'asin': asin,
            'title': self._extract_title(soup),
            'author': self._extract_author(soup),
            'price': {
                'value': None,
                'currency': None
            },
            'listPrice': {
                'value': None,
                'currency': None
            },
            'rating': {
                'stars': None,
                'count': None
            },
            'description': self._extract_description(soup),
            'features': [],
            'details': {
                'publication_date': self._extract_publication_date(soup),
                'page_count': self._extract_page_count(soup),
                'language': self._extract_language(soup),
                'isbn': self._extract_isbn(soup),
                'publisher': None,
                'dimensions': None
            },
            'categories': self._extract_categories(soup),
            'breadcrumbs': None,
            'images': {
                'primary': self._extract_image_url(soup),
                'thumbnails': []
            },
            'availability': {
                'inStock': None,
                'stockText': None
            },
            'seller': {
                'name': None,
                'id': None
            }
        }
        
        # Update price structure
        old_price = self._extract_price(soup)
        if old_price:
            book_data['price']['value'] = old_price
            book_data['price']['currency'] = '$'
            
        # Update rating structure
        old_rating = self._extract_rating(soup)
        if old_rating:
            book_data['rating']['stars'] = old_rating
            
        old_review_count = self._extract_review_count(soup)
        if old_review_count:
            book_data['rating']['count'] = old_review_count
        
        # Extract additional structured data
        self._extract_enhanced_details(soup, book_data)
        
        # Add reviews if requested
        if self.config.get('includeReviews', False):
            book_data['reviews'] = await self._scrape_reviews(book_url)
            
        return book_data
    
    def _get_realistic_headers(self, url: str = None) -> Dict[str, str]:
        """Generate realistic browser headers with rotation and context awareness."""
        # Enhanced User-Agent rotation with more realistic options
        user_agent = random.choice(self.user_agents)
        
        # Realistic header combinations based on browser type
        base_headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': random.choice([
                'en-US,en;q=0.9',
                'en-US,en;q=0.8,fr;q=0.6',
                'en-GB,en;q=0.9,en-US;q=0.8',
                'en-US,en;q=0.9,es;q=0.8'
            ]),
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': random.choice(['none', 'same-origin', 'cross-site']),
            'Sec-Fetch-User': '?1',
            'Cache-Control': random.choice(['max-age=0', 'no-cache']),
            'DNT': '1',  # Do Not Track
        }
        
        # Add realistic referrer based on navigation context
        if url and 'amazon.com' in url:
            if '/s?' in url:  # Search page
                base_headers['Referer'] = 'https://www.amazon.com/'
            elif '/dp/' in url:  # Product page
                base_headers['Referer'] = 'https://www.amazon.com/s?k=books'
            else:
                # Random referrer from common Amazon pages
                referrers = [
                    'https://www.amazon.com/',
                    'https://www.amazon.com/gp/bestsellers/books',
                    'https://www.amazon.com/books-used-books-textbooks/b?ie=UTF8&node=283155'
                ]
                base_headers['Referer'] = random.choice(referrers)
        
        # Add browser-specific headers
        if 'Chrome' in user_agent:
            chrome_version = random.choice(['119', '118', '117'])
            base_headers.update({
                'sec-ch-ua': f'"Google Chrome";v="{chrome_version}", "Chromium";v="{chrome_version}", "Not?A_Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': f'"{random.choice(["Windows", "macOS", "Linux"])}"',
                'sec-ch-ua-arch': f'"{random.choice(["x86", "arm"])}"',
                'sec-ch-ua-bitness': '"64"',
                'sec-ch-ua-full-version-list': f'"Google Chrome";v="{chrome_version}.0.0.0", "Chromium";v="{chrome_version}.0.0.0", "Not?A_Brand";v="24.0.0.0"'
            })
        elif 'Firefox' in user_agent:
            base_headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Sec-Fetch-Site': random.choice(['none', 'same-origin'])
            })
        
        # Randomly omit some headers to vary fingerprint (more realistic)
        if random.random() < 0.2:
            base_headers.pop('Cache-Control', None)
        if random.random() < 0.15:
            base_headers.pop('Upgrade-Insecure-Requests', None)
        if random.random() < 0.1:
            base_headers.pop('DNT', None)
            
        return base_headers
    
    def _is_captcha_page(self, response: Response) -> bool:
        """Enhanced CAPTCHA detection with multiple indicators."""
        content = response.text.lower()
        
        # Primary CAPTCHA indicators
        captcha_indicators = [
            'captcha',
            'robot check',
            'security check',
            'please verify',
            'are you a robot',
            'verify you are human',
            'prove you are not a robot',
            'complete the security check',
            'automated queries',
            'unusual traffic',
            'suspicious activity'
        ]
        
        # Check for CAPTCHA in content
        content_has_captcha = any(indicator in content for indicator in captcha_indicators)
        
        # Check for CAPTCHA in URL
        url_has_captcha = 'captcha' in str(response.url).lower()
        
        # Check for specific Amazon CAPTCHA patterns
        amazon_captcha_patterns = [
            'api/captcha',
            'errors/validateCaptcha',
            'ref=cs_503_logo',
            'validatecaptcha',
            'captcha.html'
        ]
        amazon_captcha = any(pattern in str(response.url).lower() for pattern in amazon_captcha_patterns)
        
        # Check response headers for CAPTCHA indicators
        headers_captcha = 'captcha' in str(response.headers).lower()
        
        # Check for Amazon-specific blocking patterns
        amazon_blocking_patterns = [
            'to discuss automated access to amazon data please contact',
            'we just need to make sure you\'re not a robot',
            'enter the characters you see below'
        ]
        amazon_blocking = any(pattern in content for pattern in amazon_blocking_patterns)
        
        return content_has_captcha or url_has_captcha or amazon_captcha or headers_captcha or amazon_blocking
    
    async def _handle_captcha_scenario(self, response: Response, attempt: int) -> bool:
        """Handle CAPTCHA scenarios with ethical and compliant strategies."""
        Actor.log.warning(f'CAPTCHA detected on attempt {attempt + 1}')
        
        # Log CAPTCHA details for analysis
        captcha_info = {
            'url': str(response.url),
            'status_code': response.status_code,
            'attempt': attempt + 1,
            'timestamp': datetime.now().isoformat()
        }
        Actor.log.info(f'CAPTCHA details: {captcha_info}')
        
        # Implement progressive backoff strategy
        if attempt == 0:
            # First CAPTCHA: Short delay, might be temporary
            delay = random.uniform(10, 20)
            Actor.log.info(f'First CAPTCHA encounter - waiting {delay:.1f}s')
        elif attempt == 1:
            # Second CAPTCHA: Medium delay, change behavior
            delay = random.uniform(30, 60)
            Actor.log.info(f'Second CAPTCHA encounter - waiting {delay:.1f}s and changing strategy')
        elif attempt == 2:
            # Third CAPTCHA: Long delay, significant behavior change
            delay = random.uniform(120, 300)
            Actor.log.info(f'Third CAPTCHA encounter - waiting {delay:.1f}s with major strategy change')
        else:
            # Multiple CAPTCHAs: Very long delay or abort
            delay = random.uniform(600, 1200)
            Actor.log.warning(f'Multiple CAPTCHA encounters - waiting {delay:.1f}s (consider aborting)')
        
        await asyncio.sleep(delay)
        
        # Return True to continue trying, False to abort
        return attempt < 3  # Allow up to 3 CAPTCHA attempts
    
    async def _adaptive_delay_strategy(self, attempt: int, error_code: int = None) -> None:
        """Implement adaptive delay strategy based on error patterns."""
        base_delay = 2.0
        
        if error_code == 503:
            # Server overload - longer delays
            delay = base_delay * (3 ** attempt) + random.uniform(10, 30)
        elif error_code == 429:
            # Rate limiting - respect and add buffer
            delay = base_delay * (2 ** attempt) + random.uniform(15, 45)
        elif error_code == 403:
            # Forbidden - possible IP block, very long delay
            delay = base_delay * (4 ** attempt) + random.uniform(30, 90)
        else:
            # General retry strategy
            delay = base_delay * (2 ** attempt) + random.uniform(5, 15)
        
        # Cap maximum delay to prevent excessive waiting
        delay = min(delay, 600)  # Max 10 minutes
        
        Actor.log.info(f'Adaptive delay for error {error_code}: {delay:.1f}s')
        await asyncio.sleep(delay)
    
    def _extract_enhanced_details(self, soup: BeautifulSoup, book_data: Dict[str, Any]) -> None:
        """Extract enhanced product details and structure them properly."""
        # Extract breadcrumbs
        if book_data['categories']:
            book_data['breadcrumbs'] = ' › '.join(book_data['categories'])
        
        # Extract features/bullet points
        features_elem = soup.find('div', {'id': 'feature-bullets'})
        if features_elem:
            feature_items = features_elem.find_all('span', class_='a-list-item')
            for item in feature_items:
                feature_text = item.get_text(strip=True)
                if feature_text and len(feature_text) > 10:
                    book_data['features'].append(feature_text)
        
        # Extract thumbnail images
        thumb_container = soup.find('div', {'id': 'altImages'})
        if thumb_container:
            thumb_imgs = thumb_container.find_all('img')
            for thumb in thumb_imgs:
                thumb_src = thumb.get('src') or thumb.get('data-src')
                if thumb_src and thumb_src not in book_data['images']['thumbnails']:
                    book_data['images']['thumbnails'].append(thumb_src)
        
        # Extract availability information
        availability_elem = soup.find('div', {'id': 'availability'}) or soup.find('span', class_='a-size-medium')
        if availability_elem:
            avail_text = availability_elem.get_text(strip=True)
            book_data['availability']['stockText'] = avail_text
            book_data['availability']['inStock'] = 'in stock' in avail_text.lower() or 'available' in avail_text.lower()
        
        # Extract seller information
        seller_elem = soup.find('span', string=re.compile(r'Ships from|Sold by', re.I))
        if seller_elem:
            seller_parent = seller_elem.find_parent()
            if seller_parent:
                seller_link = seller_parent.find('a')
                if seller_link:
                    book_data['seller']['name'] = seller_link.get_text(strip=True)
                    seller_href = seller_link.get('href', '')
                    seller_id_match = re.search(r'seller=([A-Z0-9]+)', seller_href)
                    if seller_id_match:
                        book_data['seller']['id'] = seller_id_match.group(1)
        
        # Extract enhanced product details
        details_section = soup.find('div', {'id': 'detailBullets_feature_div'}) or soup.find('div', {'id': 'productDetails_feature_div'})
        if details_section:
            detail_items = details_section.find_all('span', class_='a-list-item')
            for item in detail_items:
                text = item.get_text(strip=True)
                
                if 'Publisher' in text:
                    pub_match = re.search(r'Publisher[:\s]*([^\n;(]+)', text, re.I)
                    if pub_match:
                        book_data['details']['publisher'] = pub_match.group(1).strip()
                
                elif 'Dimensions' in text:
                    dim_match = re.search(r'Dimensions[:\s]*([^\n;]+)', text, re.I)
                    if dim_match:
                        book_data['details']['dimensions'] = dim_match.group(1).strip()
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract book title."""
        title_selectors = [
            '#productTitle',
            '.product-title',
            'h1.a-size-large'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
                
        return 'Unknown Title'
    
    def _extract_author(self, soup: BeautifulSoup) -> str:
        """Extract book author(s)."""
        author_selectors = [
            '.author .contributorNameID',
            '.author a',
            '#bylineInfo .author a'
        ]
        
        authors = []
        for selector in author_selectors:
            elements = soup.select(selector)
            for element in elements:
                author = element.get_text(strip=True)
                if author and author not in authors:
                    authors.append(author)
                    
        return ', '.join(authors) if authors else 'Unknown Author'
    
    def _extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract book price."""
        price_selectors = [
            '.a-price .a-offscreen',
            '#priceblock_dealprice',
            '#priceblock_ourprice',
            '.kindle-price .a-offscreen'
        ]
        
        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                price_match = re.search(r'\$([\d,]+\.\d{2})', price_text)
                if price_match:
                    return float(price_match.group(1).replace(',', ''))
                    
        return None
    
    def _extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract book rating."""
        rating_selectors = [
            '.a-icon-alt',
            '[data-hook="average-star-rating"] .a-icon-alt'
        ]
        
        for selector in rating_selectors:
            element = soup.select_one(selector)
            if element:
                rating_text = element.get_text(strip=True)
                rating_match = re.search(r'([\d\.]+) out of', rating_text)
                if rating_match:
                    return float(rating_match.group(1))
                    
        return None
    
    def _extract_review_count(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract number of reviews."""
        review_selectors = [
            '#acrCustomerReviewText',
            '[data-hook="total-review-count"]'
        ]
        
        for selector in review_selectors:
            element = soup.select_one(selector)
            if element:
                review_text = element.get_text(strip=True)
                review_match = re.search(r'([\d,]+)', review_text)
                if review_match:
                    return int(review_match.group(1).replace(',', ''))
                    
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract book description."""
        desc_selectors = [
            '#feature-bullets ul',
            '#bookDescription_feature_div',
            '.a-expander-content'
        ]
        
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)[:500]  # Limit description length
                
        return ''
    
    def _extract_publication_date(self, soup: BeautifulSoup) -> str:
        """Extract publication date."""
        date_element = soup.find('span', string=re.compile(r'Publication date'))
        if date_element:
            date_value = date_element.find_next('span')
            if date_value:
                return date_value.get_text(strip=True)
                
        return ''
    
    def _extract_page_count(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract page count."""
        page_element = soup.find('span', string=re.compile(r'Print length'))
        if page_element:
            page_value = page_element.find_next('span')
            if page_value:
                page_text = page_value.get_text(strip=True)
                page_match = re.search(r'(\d+)', page_text)
                if page_match:
                    return int(page_match.group(1))
                    
        return None
    
    def _extract_language(self, soup: BeautifulSoup) -> str:
        """Extract book language."""
        lang_element = soup.find('span', string=re.compile(r'Language'))
        if lang_element:
            lang_value = lang_element.find_next('span')
            if lang_value:
                return lang_value.get_text(strip=True)
                
        return ''
    
    def _extract_isbn(self, soup: BeautifulSoup) -> str:
        """Extract ISBN."""
        isbn_element = soup.find('span', string=re.compile(r'ISBN'))
        if isbn_element:
            isbn_value = isbn_element.find_next('span')
            if isbn_value:
                return isbn_value.get_text(strip=True)
                
        return ''
    
    def _extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """Extract book categories."""
        categories = []
        breadcrumb = soup.select('#wayfinding-breadcrumbs_feature_div a')
        
        for link in breadcrumb:
            category = link.get_text(strip=True)
            if category and category not in ['Books', 'Kindle Store']:
                categories.append(category)
                
        return categories
    
    def _extract_image_url(self, soup: BeautifulSoup) -> str:
        """Extract book cover image URL."""
        img_selectors = [
            '#landingImage',
            '.a-dynamic-image',
            '#ebooksImgBlkFront'
        ]
        
        for selector in img_selectors:
            element = soup.select_one(selector)
            if element and element.get('src'):
                return element['src']
                
        return ''
    
    async def _scrape_reviews(self, book_url: str) -> List[Dict[str, Any]]:
        """Scrape customer reviews for the book."""
        # Extract ASIN from book URL for reviews
        asin_match = re.search(r'/dp/([A-Z0-9]{10})', book_url)
        if not asin_match:
            return []
            
        asin = asin_match.group(1)
        reviews_url = f"{self.base_url}/product-reviews/{asin}"
        
        response = await self._make_request(reviews_url)
        if not response:
            return []
            
        soup = BeautifulSoup(response.content, 'lxml')
        reviews = []
        
        review_containers = soup.find_all('div', {'data-hook': 'review'})
        
        for container in review_containers[:10]:  # Limit to 10 reviews
            review_data = {
                'rating': self._extract_review_rating(container),
                'title': self._extract_review_title(container),
                'text': self._extract_review_text(container),
                'author': self._extract_review_author(container),
                'date': self._extract_review_date(container)
            }
            reviews.append(review_data)
            
        return reviews
    
    def _extract_review_rating(self, container) -> Optional[float]:
        """Extract rating from review container."""
        rating_element = container.find('i', class_='a-icon-star')
        if rating_element:
            rating_text = rating_element.get_text(strip=True)
            rating_match = re.search(r'([\d\.]+)', rating_text)
            if rating_match:
                return float(rating_match.group(1))
        return None
    
    def _extract_review_title(self, container) -> str:
        """Extract title from review container."""
        title_element = container.find('a', {'data-hook': 'review-title'})
        if title_element:
            return title_element.get_text(strip=True)
        return ''
    
    def _extract_review_text(self, container) -> str:
        """Extract text from review container."""
        text_element = container.find('span', {'data-hook': 'review-body'})
        if text_element:
            return text_element.get_text(strip=True)[:300]  # Limit review text
        return ''
    
    def _extract_review_author(self, container) -> str:
        """Extract author from review container."""
        author_element = container.find('span', class_='a-profile-name')
        if author_element:
            return author_element.get_text(strip=True)
        return ''
    
    def _extract_review_date(self, container) -> str:
        """Extract date from review container."""
        date_element = container.find('span', {'data-hook': 'review-date'})
        if date_element:
            return date_element.get_text(strip=True)
        return ''
    
    def _meets_criteria(self, book_data: Dict[str, Any]) -> bool:
        """Check if book meets the filtering criteria."""
        # Check minimum rating
        min_rating = self.config.get('minRating', 0)
        if book_data.get('rating') and book_data['rating'] < min_rating:
            return False
            
        # Check price range
        price_range = self.config.get('priceRange', {})
        if book_data.get('price'):
            min_price = price_range.get('min', 0)
            max_price = price_range.get('max', float('inf'))
            if not (min_price <= book_data['price'] <= max_price):
                return False
                
        return True


async def main() -> None:
    """Main entry point for the Amazon KDP Book Scraper Actor."""
    async with Actor:
        # Get input configuration
        actor_input = await Actor.get_input() or {}
        Actor.log.info(f'Actor input received: {actor_input}')
        
        # For local testing, use default values if no input provided
        if not actor_input:
            actor_input = {
                'searchTerms': ['python programming'],
                'maxResults': 5,
                'includeReviews': False,
                'minRating': 0,
                'sortBy': 'relevance',
                'requestDelay': 3
            }
            Actor.log.info('Using default test configuration for local testing')
        
        # Validate required inputs
        search_terms = actor_input.get('searchTerms', [])
        Actor.log.info(f'Search terms found: {search_terms}')
        if not search_terms:
            raise ValueError('At least one search term is required!')
            
        Actor.log.info(f'Starting Amazon KDP scraper with {len(search_terms)} search terms')
        
        # Configure HTTP client with proxy if specified and session management
        proxy_config = actor_input.get('proxyConfiguration', {})
        client_kwargs = {
            'timeout': 60.0,
            'cookies': {},
            'limits': httpx.Limits(max_keepalive_connections=5, max_connections=10)
        }
        
        # Force Apify proxy usage if no proxy configuration is provided
        if not proxy_config:
            proxy_config = {'useApifyProxy': True}
            Actor.log.info('No proxy configuration provided, automatically enabling Apify proxy')
        
        if proxy_config.get('useApifyProxy'):
            # Use Apify proxy format with proper authentication
            import os
            proxy_password = os.getenv('APIFY_PROXY_PASSWORD')
            proxy_hostname = os.getenv('APIFY_PROXY_HOSTNAME', 'proxy.apify.com')
            proxy_port = os.getenv('APIFY_PROXY_PORT', '8000')
            
            if proxy_password:
                proxy_url = f"http://auto:{proxy_password}@{proxy_hostname}:{proxy_port}"
                client_kwargs['proxies'] = proxy_url
                Actor.log.info('Using Apify proxy for requests with session management')
            else:
                Actor.log.warning('APIFY_PROXY_PASSWORD not found, proceeding without proxy')
                Actor.log.info('Note: Apify Proxy requires authentication - check your proxy configuration')
        elif proxy_config.get('proxyUrls'):
            proxy_url = proxy_config['proxyUrls'][0]
            client_kwargs['proxies'] = proxy_url
            Actor.log.info(f'Using custom proxy with session management: {proxy_url}')
            
        async with AsyncClient(**client_kwargs) as client:
            scraper = AmazonKDPScraper(client, actor_input)
            
            all_books = []
            categories = actor_input.get('categories', [None])
            
            # Process each search term and category combination
            for search_term in search_terms:
                for category in categories:
                    try:
                        books = await scraper.search_books(search_term, category)
                        all_books.extend(books)
                        
                        Actor.log.info(f'Found {len(books)} books for "{search_term}" in category "{category}"')
                        
                        # Add delay between different searches
                        if len(search_terms) > 1 or len(categories) > 1:
                            await asyncio.sleep(actor_input.get('requestDelay', 2))
                            
                    except Exception as e:
                        Actor.log.error(f'Error processing search term "{search_term}": {str(e)}')
                        continue
            
            # Remove duplicates based on URL
            unique_books = []
            seen_urls = set()
            
            for book in all_books:
                if book['url'] not in seen_urls:
                    unique_books.append(book)
                    seen_urls.add(book['url'])
                    
            Actor.log.info(f'Scraped {len(unique_books)} unique books total')
            
            # Save results to dataset
            if unique_books:
                await Actor.push_data(unique_books)
            else:
                Actor.log.warning('No books found matching the criteria')


if __name__ == '__main__':
    asyncio.run(main())
