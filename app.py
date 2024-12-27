from flask import Flask, render_template, request, send_from_directory
import requests
from bs4 import BeautifulSoup
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import re
from datetime import datetime
from urllib.parse import urlparse

app = Flask(__name__)

# Google API Key
API_KEY = "AIzaSyDYm825noVtzZLnT8ms8sl2fpq-P1FvG1A"

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session = requests.Session()
session.mount("http://", adapter)
session.mount("https://", adapter)

def is_mobile_friendly(html_content):
    """Check mobile-friendliness based on common indicators"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Check for viewport meta tag
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    
    # Check for responsive design indicators
    media_queries = bool(re.search(r'@media', str(soup.find_all('style'))))
    
    # Check for mobile-specific meta tags
    mobile_meta = soup.find('meta', attrs={'name': 'mobile-web-app-capable'})
    apple_meta = soup.find('meta', attrs={'name': 'apple-mobile-web-app-capable'})
    
    # Count points for mobile-friendliness
    points = 0
    if viewport:
        points += 1
    if media_queries:
        points += 1
    if mobile_meta or apple_meta:
        points += 1
    
    return "Likely Mobile-Friendly" if points >= 2 else "May Not Be Mobile-Friendly"

def estimate_page_speed(html_content, response_time):
    """Estimate page speed based on content size and response time"""
    content_size = len(html_content) / 1024  # Size in KB
    
    # Basic scoring based on response time and content size
    score = 100
    
    # Penalize for slow response time
    if response_time > 1:
        score -= (response_time - 1) * 10
    
    # Penalize for large page size
    if content_size > 500:  # If page is larger than 500KB
        score -= (content_size - 500) / 100
    
    return max(0, min(100, score))  # Keep score between 0 and 100

# Function to check mobile-friendliness
def check_mobile_friendly(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        start_time = time.time()
        response = session.get(url, headers=headers, timeout=30)
        response_time = time.time() - start_time
        
        response.raise_for_status()
        return is_mobile_friendly(response.text)
    except Exception as e:
        return f"Error checking mobile-friendliness: {str(e)}"

# Function to check page speed
def check_page_speed(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        start_time = time.time()
        response = session.get(url, headers=headers, timeout=30)
        response_time = time.time() - start_time
        
        response.raise_for_status()
        speed_score = estimate_page_speed(response.text, response_time)
        return round(speed_score, 2)
    except Exception as e:
        return f"Error checking page speed: {str(e)}"

# Function to check schema markup
def check_schema(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        schema = soup.find_all("script", type="application/ld+json")
        return "Present" if schema else "Absent"
    except Exception as e:
        return f"Error checking schema: {str(e)}"

# Function to check content freshness
def check_freshness(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Check Last-Modified header
        last_modified = response.headers.get("Last-Modified")
        if last_modified:
            return last_modified
            
        # Check for date patterns in the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for common date meta tags
        meta_date = soup.find('meta', attrs={'property': 'article:published_time'})
        if meta_date:
            return meta_date['content']
            
        # Look for visible dates in the content
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\w+ \d{1,2}, \d{4}'  # Month DD, YYYY
        ]
        
        for pattern in date_patterns:
            dates = re.findall(pattern, response.text)
            if dates:
                return dates[0]
                
        return "Date not found"
    except Exception as e:
        return f"Error checking freshness: {str(e)}"

# Route for the home page
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        url = request.form.get("url")
        
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return render_template("index.html", 
                                result={"error": "Please enter a valid URL starting with http:// or https://"})
        
        try:
            # Parse URL to ensure it's valid
            parsed_url = urlparse(url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                return render_template("index.html",
                                    result={"error": "Invalid URL format"})
            
            # Perform checks with delay between each
            mobile_friendly = check_mobile_friendly(url)
            time.sleep(1)
            
            page_speed = check_page_speed(url)
            time.sleep(1)
            
            schema_status = check_schema(url)
            time.sleep(1)
            
            freshness = check_freshness(url)

            # Analyze results
            is_optimized = (
                "Mobile-Friendly" in str(mobile_friendly) and
                isinstance(page_speed, (int, float)) and
                not isinstance(page_speed, str) and
                page_speed > 80 and
                schema_status == "Present"
            )

            result = {
                "url": url,
                "mobile_friendly": mobile_friendly,
                "page_speed": page_speed,
                "schema_status": schema_status,
                "freshness": freshness,
                "is_optimized": is_optimized
            }
            return render_template("index.html", result=result)
            
        except Exception as e:
            return render_template("index.html",
                                result={"error": f"Error analyzing URL: {str(e)}"})

    return render_template("index.html", result=None)

# Route for About Us page
@app.route("/about")
def about():
    return render_template("about.html")

# Route for Contact Us page
@app.route("/contact")
def contact():
    return render_template("contact.html")

# Route for Privacy Policy page
@app.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")

# Route for Terms & Conditions page
@app.route("/terms-conditions")
def terms_conditions():
    return render_template("terms_conditions.html")

# Route for robots.txt
@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt')

# Route for sitemap.xml
@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml')

if __name__ == "__main__":
    app.run(debug=True)
