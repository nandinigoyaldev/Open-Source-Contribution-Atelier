import asyncio
import aiohttp
import argparse
import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup
import markdown
from colorama import init, Fore, Style

init(autoreset=True)

# Configuration
CONCURRENCY_LIMIT = 50
MAX_RETRIES = 3
RETRY_DELAY = 2  # Seconds
TIMEOUT = 15

# Ignore these domains explicitly
EXCLUDE_DOMAINS = [
    r'localhost',
    r'127\.0\.0\.1',
    r'.*\.local',
    r'example\.com',
]

def extract_links_from_markdown(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            md_text = f.read()
    except Exception as e:
        print(Fore.RED + f"Failed to read {file_path}: {e}")
        return set()

    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if href.startswith('mailto:') or href.startswith('#') or not href:
            continue
        links.add(href)
    return links

async def check_url(session, url, file_path, semaphore):
    # Check if ignored
    for pattern in EXCLUDE_DOMAINS:
        if re.search(pattern, url):
            return (url, "IGNORED", file_path)

    # Check local relative paths
    if not url.startswith('http'):
        # Resolve against the markdown file's directory
        local_path = file_path.parent / url
        if local_path.exists():
            return (url, "OK", file_path)
        else:
            return (url, "BROKEN_LOCAL", file_path)

    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Use a real browser user agent
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36"}
                async with session.head(url, timeout=TIMEOUT, headers=headers, allow_redirects=True) as response:
                    if response.status in [200, 429, 403]:  # Accept rate limits and strict WAFs as soft success
                        return (url, "OK", file_path)
                    if response.status == 405: # Method not allowed, try GET
                        async with session.get(url, timeout=TIMEOUT, headers=headers, allow_redirects=True) as get_response:
                            if get_response.status in [200, 429, 403]:
                                return (url, "OK", file_path)
                            else:
                                return (url, f"HTTP_{get_response.status}", file_path)
                    
                    if response.status >= 500 and attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY * attempt)
                        continue
                    
                    return (url, f"HTTP_{response.status}", file_path)
            except asyncio.TimeoutError:
                if attempt == MAX_RETRIES:
                    return (url, "TIMEOUT", file_path)
                await asyncio.sleep(RETRY_DELAY * attempt)
            except Exception as e:
                if attempt == MAX_RETRIES:
                    return (url, "ERROR", file_path)
                await asyncio.sleep(RETRY_DELAY * attempt)

async def process_files(directory_or_files):
    files_to_check = []
    base_dir = Path.cwd().resolve()
    
    # If a list of files is provided via args
    for item in directory_or_files:
        path = Path(item).resolve()
        
        # Prevent path traversal outside the current working directory
        try:
            path.relative_to(base_dir)
        except ValueError:
            print(Fore.RED + f"Security Error: Path '{item}' is outside the allowed directory.")
            continue

        if path.is_file() and path.suffix == '.md':
            files_to_check.append(path)
        elif path.is_dir():
            files_to_check.extend(path.rglob('*.md'))

    if not files_to_check:
        print(Fore.YELLOW + "No Markdown files found to check.")
        return 0

    print(Fore.CYAN + f"Scanning {len(files_to_check)} markdown files...")

    link_map = {}
    for f in files_to_check:
        links = extract_links_from_markdown(f)
        for link in links:
            if link not in link_map:
                link_map[link] = []
            link_map[link].append(f)

    if not link_map:
        print(Fore.GREEN + "No external or internal links found in the scanned files.")
        return 0

    print(Fore.CYAN + f"Found {len(link_map)} unique links. Validating concurrently...")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = []

    # Configure session with connection pooling
    conn = aiohttp.TCPConnector(limit=CONCURRENCY_LIMIT)
    async with aiohttp.ClientSession(connector=conn) as session:
        for url, file_paths in link_map.items():
            tasks.append(check_url(session, url, file_paths[0], semaphore))

        results = await asyncio.gather(*tasks)

    broken_links = []
    for url, status, file_path in results:
        if status not in ["OK", "IGNORED"]:
            broken_links.append((url, status, link_map[url]))

    print("\n" + "="*50)
    print(Fore.CYAN + f"Link Validation Report")
    print("="*50)

    if not broken_links:
        print(Fore.GREEN + f"✅ All {len(link_map)} links are healthy!")
        return 0

    print(Fore.RED + f"❌ Found {len(broken_links)} broken links:\n")
    for url, status, files in broken_links:
        print(Fore.RED + f"[{status}] " + Fore.WHITE + f"{url}")
        for f in files:
            print(Fore.YELLOW + f"  └── {f}")
        print("")

    # Generate Markdown Report for GitHub Actions
    with open('link_audit_report.md', 'w', encoding='utf-8') as f:
        f.write("# 🚨 Broken Links Report\n\n")
        f.write(f"The automated async link checker found **{len(broken_links)}** broken links.\n\n")
        for url, status, files in broken_links:
            f.write(f"### `{status}`: {url}\n")
            for file in files:
                f.write(f"- Found in: `{file}`\n")
            f.write("\n")

    return 1

def main():
    parser = argparse.ArgumentParser(description="Advanced Async Link Validator")
    parser.add_argument('paths', nargs='+', help="Files or directories to scan")
    args = parser.parse_args()

    # Create event loop correctly for Windows compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    exit_code = asyncio.run(process_files(args.paths))
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
