import time
from urllib.request import Request, urlopen

# Test URL from Google News
test_url = "https://news.google.com/rss/articles/CBMiQGh0dHBzOi8vd3d3LmNubi5jb20vMjAyNC8wNC8wMy9wb2xpdGljcy90cnVtcC1zbmwteWFuZy1tYXNrLWdhamkvaTWSAQA?oc=5"

# Create request with headers to avoid being blocked
req = Request(
    test_url,
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }
)

print(f"Testing Google News redirect for URL: {test_url}")

try:
    # Time the redirect
    redirect_start = time.time()
    response = urlopen(req, timeout=15)
    final_url = response.geturl()
    redirect_time = time.time() - redirect_start

    print(f"Redirect successful!")
    print(f"Original URL: {test_url}")
    print(f"Final URL: {final_url}")
    print(f"Redirect time: {redirect_time:.2f} seconds")

except Exception as e:
    print(f"Error during redirect: {e}")
