import traceback
import os.path
import json
import csv
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import random
import time
from typing import Optional, List
from dataclasses import dataclass
from pathlib import Path
import argparse
import sys

from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
import requests
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
import pandas as pd

CSV_KEYS = [
    'URL',
    'Name',
    'What is (s)he an instructor in',
    'Instructor_Photo_URL',
    'Description',
    'Total Learners',
    'Total Reviews',
    'Social Website',
    'Social Youtube',
    'Social Facebook',
    'Social Linkedin',
    'Social Twitter',
    'Course Title',
    'Course URL',
    'Total number of lectures',
    'Total number of reviews',
    'Course Rating',
    'Content Info',
    'Course Price',
]

@dataclass
class ScraperConfig:
    """Configuration class for Udemy scraper with sensible defaults."""
    
    def __init__(
        self,
        output_file: str = "udemy courses.csv",       # Output CSV filename
        threads: int = 1,                             # Number of concurrent threads
        proxies: Optional[str] = None,                # Proxies string
        delay: float = 5.0,                           # Delay between page requests
        clean: bool = False,                          # Start clean scrape, ignore progress
        urls_file: str = "urls.txt",                  # File containing instructor URLs
        max_retries: int = 5,                         # Maximum retry attempts per URL
        headless: bool = True,                        # Run browser in headless mode
        browser_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ):
        self.output_file = output_file
        self.threads = threads
        self.proxies = proxies
        self.delay = delay
        self.clean = clean
        self.urls_file = urls_file
        self.max_retries = max_retries
        self.headless = headless
        self.browser_agent = browser_agent
    
    @classmethod
    def from_args(cls, args):
        """Create a ScraperConfig instance from parsed command line arguments."""
        config = cls()
        
        # Update config with command line arguments if they're provided
        if args.output is not None:
            config.output_file = args.output
            
        if args.threads is not None:
            config.threads = args.threads
            
        if args.proxies is not None:
            config.proxies = args.proxies
            
        if args.delay is not None:
            config.delay = args.delay
            
        if args.clean is not None:
            config.clean = args.clean
            
        if args.urls_file is not None:
            config.urls_file = args.urls_file
            
        if args.max_retries is not None:
            config.max_retries = args.max_retries
            
        # Only override headless if the flag was actually provided
        if '--headless' in sys.argv:
            config.headless = args.headless
            
        return config

def get_captured_responses(driver, filter_url=None):
    """
    Retrieve captured responses, optionally filtering by URL.
    Call this after the page has loaded and all API calls have completed.
    """
    if not hasattr(driver, 'response_data'):
        print("No response data available. Did you call setup_network_interception?")
        return []
    
    if filter_url:
        return [resp for resp in driver.response_data if filter_url in resp['url']]
    return driver.response_data

def setup_network_interception(driver):
    """
    Set up network interception to capture API responses.
    Must be called BEFORE navigating to the page.
    """
    # Enable necessary CDP domains
    driver.execute_cdp_cmd('Network.enable', {})
    
    # Create a list to store response data
    driver.response_data = []
    
    # Define a callback to handle Network.responseReceived events
    def response_received(data):
        request_id = data['requestId']
        response = data['response']
        url = response['url']
        
        # Only capture API responses we're interested in
        if '/api/taught-courses' in url or '/api/instructors' in url:
            try:
                # Get the response body
                response_body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                driver.response_data.append({
                    'url': url,
                    'status': response['status'],
                    'body': response_body.get('body', '')
                })
            except Exception as e:
                print(f"Error getting response body for {url}: {e}")
    
    # Add event listener for Network.responseReceived
    driver.execute_cdp_cmd('Network.responseReceived', response_received)
    
def check_profile_validity(driver, url):
    try:
        error_greeting_elements = driver.find_elements(By.CSS_SELECTOR, 'h1[class*="error__greeting"]')
        if error_greeting_elements and "Oops!" in error_greeting_elements[0].text:
            print(f"Profile not found (Oops!): {url}")
            return False
    except:
        pass

    try:
        # More robust selector for private profile
        private_profile_elements = driver.find_elements(By.XPATH, 
            "//h1[contains(text(), 'This profile is private')] | //div[contains(@class, 'private-profile--container')] | //*[contains(text(), 'profile is private') and (self::h1 or self::h2 or self::p)]"
        )
        if private_profile_elements:
            print(f"Profile is private: {url}")
            return False
    except:
        pass
        
    return True

def get_webdriver(headless=False, browser_agent=None):        
    options = uc.ChromeOptions()
    
    # Enable analyzing API requests
    options.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})
    
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    
    width = random.randint(1050, 1200)
    height = random.randint(800, 950)
    options.add_argument(f"--window-size={width},{height}")
    
    if browser_agent:
        options.add_argument(f"--user-agent={browser_agent}")
    
    driver = uc.Chrome(
        options=options,
        version_main=None,
        use_subprocess=True,
        browser_executable_path=None,
        headless=headless,
        # Let it find or download the appropriate driver
        driver_executable_path=None,
    )
    
    # Apply additional anti-detection measures
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def get_list_of_teachers(config):
    """
    Scrape and store list of all instructor URLs on Udemy.
    
    @param clean_scrape - If True, re-scrape the list.
    If False, read list from a file, if file exists, otherwise fetch the list from sitemap.
    """
    urls = []
    
    if config.clean and os.path.exists(config.urls_file):
        os.remove(config.urls_file)
    
    # if the list was scraped already, return that list of instructors
    if os.path.exists(config.urls_file):
        with open(config.urls_file, 'r') as f:
            lines = [line.strip() for line in f.readlines()]
            urls = lines
            
        return urls
    
    # get all instructor sitemap URLs
    response = requests.get('https://www.udemy.com/sitemap.xml')
    sitemap_urls = []
    
    for line in BeautifulSoup(response.text).select('loc'):
        if 'https://www.udemy.com/sitemap/instructors.xml?p=' not in line.text:
            continue
        sitemap_urls.append(line)
    
    # each instructor sitemap file contains about 100 instructors,
    # iterate through all of them
    for i in sitemap_urls:
        
        proxies = None
        
        if config.proxies:
            proxies = { 
                "http": config.proxies, 
                "https": config.proxies,
            }
        
        url = 'https://www.udemy.com/sitemap/instructors.xml?p=' + str(i)
        response = requests.get(url, proxies=proxies)
        
        for line in BeautifulSoup(response.text).select('loc'):
            if 'https:' in line.text:
                urls.append(line.text.strip())
        
        time.sleep(config.delay)
        
    with open(config.urls_file, 'w') as f:
        f.write('\n'.join(urls))
        
    return urls

def process_browser_log_entry(entry):
    response = json.loads(entry['message'])['message']
    return response

def get_network_data(driver, events=None, return_events=False):
    browser_log = driver.get_log('performance')
    all_events = [process_browser_log_entry(entry) for entry in browser_log]
    
    if events:
        all_events.extend(events)
    
    response_events = [event for event in all_events if 'Network.response' in event['method']]
    request_events = [event for event in all_events if 'Network.request' in event['method']]

    # map requestId to postData
    post_data = {}
    for event in request_events:
        try:
            post_data[event['params']['requestId']] = json.loads(event['params']['request']['postData'])
        except Exception:
            continue
    
    # possibly transform data into [{'Url': .., 'Data': ..}..]
    data = []
    for event in response_events:
        try:
            url = event['params']['response']['url']
            body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': event["params"]["requestId"]})['body']
            
            try:
                request_payload = post_data[event['params']['requestId']]
            except Exception:
                request_payload = ''
                
            timestamp = event['params']['timestamp'] if 'timestamp' in event['params'] else 0
            
            data.append({
                'Url': url, 
                'Data': body, 
                'PostData': request_payload,
                'Timestamp': timestamp
            })
            
        except Exception:
            continue
    
    if return_events:
        return data, all_events
    else:
        return data

def extract_courses_from_api_data(api_data):
    """
    Extracts course information from the API data collected.
    """
    courses = []
    
    for entry in api_data:
        try:
            # Handle course data
            if 'taught-profile-courses' not in entry['Url']:
                continue
            
            data = json.loads(entry['Data'].strip())
            course_results = data.get('results', [])
            
            for course in course_results:
                course_info = {
                    'Course Title': course.get('title', ''),
                    'Course URL': 'https://www.udemy.com' + course.get('url', ''),
                    'Total number of lectures': course.get('num_published_lectures', ''),
                    'Total number of reviews': course.get('num_reviews', ''),
                    'Course Rating': course.get('rating', ''),
                    'Content Info': course.get('content_info', '')
                }
                
                # Extract pricing info
                if 'price_detail' in course and course['price_detail']:
                    course_info['Course Price'] = course.get('price_detail', {}).get('price_string', '')
                elif 'price' in course:
                    course_info['Course Price'] = course['price']
                
                courses.append(course_info)
                
        except Exception as e:
            print(f"Error processing API data from {entry['Url']}: {e}")
    
    return courses

def parse_instructor(driver):
    """
    Parses the HTML content from the Selenium WebDriver to extract instructor information.

    Args:
        driver: A Selenium WebDriver object that has loaded the instructor page.

    Returns:
        A dictionary containing the parsed instructor information.
    """
    try:
    
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        
        instructor_data = {}
    
        # Instructor Name
        name_tag = soup.select_one('h1[class*="title-area-module--instructor-name"]')
        instructor_data['Name'] = name_tag.text.strip() if name_tag else None
    
        # Instructor Headline/Title
        headline_tag = soup.select_one('h1[class*="title-area-module--instructor-title"]')
        instructor_data['What is (s)he an instructor in'] = headline_tag.text.strip() if headline_tag else None
    
        # Instructor Image URL
        image_tag = soup.select_one('img[class*="sidebar-area-module--sidebar-image"]')
        instructor_data['Instructor_Photo_URL'] = image_tag['src'] if image_tag and image_tag.has_attr('src') else None
    
        # Instructor Description
        description_div = soup.select_one('div[data-purpose="instructor-description"]')
        if description_div:
            instructor_data['Description'] = description_div.get_text(separator='\n', strip=True)
        else:
            instructor_data['Description'] = None
            
        # Instructor Stats
        for stat in soup.select('div[class*="value-props-module--body"]'):
            stat_key = stat.select_one('div[class*="value-props-module"]').text.strip().lower()
            
            if stat_key == 'total learners':
                instructor_data['Total Learners'] = stat.select_one('div[class*="ud-heading-md"]').text.strip()
                
            elif stat_key == 'reviews':
                instructor_data['Total Reviews'] = stat.select_one('div[class*="ud-heading-md"]').text.strip()

        # Social Links
        for link_tag in soup.select('div[class*="social-links-module--sidebar-social-links"] > a'):
            href = link_tag.get('href')
            svg_icon = link_tag.select_one('svg use')
            icon_name = svg_icon['xlink:href'].replace('#icon-', '').title()
            
            if icon_name == "Link":
                # Personal website
                instructor_data['Social Website'] = href
            else:
                instructor_data['Social ' + icon_name] = href
        
        return instructor_data
    
    except Exception:
        traceback.print_exc()
        
def get_displayed_courses(driver):
    """
    Return list of course titles on displayed page as string, separated by comma.
    This is used to check if next course page is loaded and displayed properly.
    """
    return ','.join([course.text for course in driver.find_elements(By.CSS_SELECTOR, 'h3[class*="card-title-module--title"]')])
    
def is_next_course_page_loaded(driver, current_courses):
    try:
        displayed_courses = get_displayed_courses(driver)
        if not displayed_courses:
            return False
        
        if displayed_courses == current_courses:
            return False
        
        return True
        
    except Exception:
        return False
    
def iterate_courses(driver):
    """
    Repeatedly click on next course page until all pages are loaded.
    """
    counter = 0
    
    while driver.find_elements(By.CSS_SELECTOR, 'a[class*="pagination-module--next"]:not(.ud-btn-disabled)'):
        
        counter += 1
        if counter > 100:
            raise Exception('Something went wrong')
        
        displayed_courses = get_displayed_courses(driver)
        next_button = driver.find_element(By.CSS_SELECTOR, 'a[class*="pagination-module--next"]:not(.ud-btn-disabled)')
        driver.execute_script("arguments[0].scrollIntoView();", next_button)
        next_button.click()
        WebDriverWait(driver, 30).until(lambda driver: is_next_course_page_loaded(driver, displayed_courses))

def scrape_teacher(config, teacher_url, tries):
    try:
        driver = get_webdriver(config.headless, config.browser_agent)
        driver.get(teacher_url)
        
        # Wait for page to load
        time.sleep(6)
        
        # Check if profile exists
        if driver.find_elements(By.CSS_SELECTOR, 'h1[class*="error__greeting"]'):
            if 'Oops!' in driver.find_element(By.CSS_SELECTOR, 'h1[class*="error__greeting"]').text:
                print(f"Profile not found (Oops!): {teacher_url}")
                driver.quit()
                return []

        # Check if profile is private
        private_profile_elements = driver.find_elements(By.XPATH, "//h1[contains(text(), 'This profile is private')]")
        if private_profile_elements:
            print(f"Profile is private: {teacher_url}")
            driver.quit()
            return []
        
        instructor = parse_instructor(driver)
        instructor['URL'] = teacher_url
        
        # Iterate all course pages to get all course data
        iterate_courses(driver)
        api_data = get_network_data(driver)
        courses = extract_courses_from_api_data(api_data)
        driver.quit()
        time.sleep(config.delay)
        
        # If no course data, return just instructor data
        if not courses:
            return [instructor]
        
        # Return courses with instructor information
        return [{**instructor, **course} for course in courses]
        
    except Exception as e:
        print(f"An error occurred in scrape_teacher for {teacher_url}: {e}")
        traceback.print_exc()
        driver.quit()
            
        tries -= 1
        if tries == 0:
            print(f"Final attempt failed for {teacher_url}. Error: {e}")
            return []
        
        print(f"Retrying {teacher_url}, {tries} attempts left.")
        time.sleep(20 + (3-tries)*10)
            
        return scrape_teacher(config, teacher_url, tries)
    
    finally:
        driver.quit()
    
def parse_arguments():
    parser = argparse.ArgumentParser(description='Udemy Instructor Scraper')
    
    parser.add_argument('--output', '-o', help='Output CSV filename')
    parser.add_argument('--threads', '-t', type=int, help='Number of threads to use')
    parser.add_argument('--proxies', '-p', help='Proxies in format {IP:port}')
    parser.add_argument('--delay', '-d', type=float, help='Delay between requests in seconds')
    parser.add_argument('--clean', '-c', action='store_true', help='Start clean scrape')
    parser.add_argument('--urls-file', help='File containing instructor URLs')
    parser.add_argument('--max-retries', type=int, help='Maximum retry attempts per URL')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--browser-agent', help='Set browser agent string')
    
    return parser.parse_args()
    
def scrape_teachers(config, urls):
    
    if config.clean:
        os.remove(config.output_file)
    
    output_file_exists = os.path.exists(config.output_file)
    write_mode = 'w'
    
    if output_file_exists:
        scraped_data = pd.read_csv(config.output_file).to_dict('records')
        scraped_urls = {s_d['URL'] for s_d in scraped_data}
        urls = [url for url in urls if url not in scraped_urls]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.threads) as executor:

        future_to_url = {executor.submit(scrape_teacher, config, url, config.max_retries): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            data = future.result()
            
            if output_file_exists:
                write_mode = 'a'
            
            with open(config.output_file, write_mode, encoding='utf8') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames = CSV_KEYS, delimiter=',', lineterminator='\n', extrasaction='ignore', quoting=csv.QUOTE_NONNUMERIC, escapechar='\\')
                
                if not output_file_exists:
                    dict_writer.writeheader()
                    
                dict_writer.writerows(data)
                output_file_exists = True
            
if __name__ == '__main__':
    args = parse_arguments()
    
    # Create configuration from command line arguments
    config = ScraperConfig.from_args(args)
    
    urls = get_list_of_teachers(config)
    scrape_teachers(config, urls)
            