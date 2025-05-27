# Udemy Scraper

A Python script to get instructor profiles and their course details from Udemy. It uses Selenium and `undetected-chromedriver` to grab data and saves it to a CSV file.

## Disclaimer

**For educational purposes only.** Please respect Udemy's Terms of Service.

## Quick Start

1.  **Clone:**
    ```bash
    git clone https://github.com/Michael58/udemy.git
    cd udemy
    ```

2.  **Set up (optional but good):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

3.  **Install stuff:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run it!**
    ```bash
    python udemy_scraper.py
    ```
    This will:
    *   Find instructor URLs (or use `urls.txt` if it's there).
    *   Get instructor and course info.
    *   Save to `udemy courses.csv`.

## Main Features

*   Gets instructor info (name, bio, photo, social links).
*   Gets course info (title, URL, lectures, reviews, rating, price).
*   Finds instructors from Udemy's sitemaps.
*   Tries to avoid being blocked by Udemy.
*   Can use multiple threads to run faster.
*   Saves instructor URLs to `urls.txt` so it doesn't have to find them every time.
*   Can pick up where it left off if you run it again (unless you use `--clean`).
*   Saves data to a CSV.

## Requirements

*   Python 3.7+
*   Google Chrome browser

## More Ways to Run

**More threads, different output file:**
```bash
python udemy_scraper.py --threads 5 --output my_udemy_data.csv
```

**Start fresh (ignores old `urls.txt` and output file):**
```bash
python udemy_scraper.py --clean
```

**Use a proxy:**
```bash
python udemy_scraper.py --proxies "http://user:pass@yourproxy.com:port"
```

## Command Line Options

*   `--output` / `-o`: Output CSV file name (default: `"udemy courses.csv"`)
*   `--threads` / `-t`: How many threads to use (default: `1`)
*   `--proxies` / `-p`: Proxy server (e.g., `"http://user:pass@host:port"`)
*   `--delay`: Wait time in seconds between some actions (default: `5.0`)
*   `--clean` / `-c`: Start fresh, ignore old files.
*   `--urls-file`: File for instructor URLs (default: `"urls.txt"`)
*   `--max-retries`: How many times to retry a failed URL (default: `5`)
*   `--headless`: Run browser without showing it (default is on).
*   `--browser-agent`: Custom browser ID string.

## How It Works

1.  Reads settings from command line or uses defaults.
2.  Finds instructor URLs (from `urls.txt` or Udemy sitemaps).
3.  For each instructor:
    *   Opens their page in a hidden Chrome browser.
    *   Grabs instructor details from the HTML.
    *   Clicks through all their course pages.
    *   Catches the course data sent by Udemy's server.
4.  Saves all data to a CSV file. If the script stopped, it tries to continue from where it left off next time.

## Output CSV Fields

-   `URL`: Instructor's profile URL.
-   `Name`: Instructor's name.
-   `What is (s)he an instructor in`: Instructor's title.
-   `Instructor_Photo_URL`: Profile picture URL.
-   `Description`: Instructor's bio.
-   `Total Learners`: Instructor's total students.
-   `Total Reviews`: Instructor's total reviews.
-   `Social Website`, `Social Youtube`, etc.: Social media links.
-   `Course Title`: Course name.
-   `Course URL`: Link to the course.
-   `Total number of lectures`: Lectures in the course.
-   `Total number of reviews`: Reviews for the course.
-   `Course Rating`: Course rating.
-   `Content Info`: Course length (e.g., "10.5 total hours").
-   `Course Price`: Course price.

## Notes

*   Websites change. If Udemy changes, this script might break.
*   Be nice to Udemy's servers. Don't use too many threads or too little delay.

## License

This project is licensed under the MIT License.

Copyright (c) 2025 Michal Búci

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.