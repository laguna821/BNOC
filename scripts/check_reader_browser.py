"""Exercise the latest pinned weekly reading before Pages can deploy it."""
import functools
import json
import shutil
import subprocess
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    issues = [json.loads(path.read_text(encoding="utf-8")) for path in (ROOT / "issues").glob("*.json")]
    readers = [issue for issue in issues if issue.get("publicationStatus") == "published"
               and issue.get("versions", {}).get("skill") == "bnoc-passage-reader"
               and issue["versions"].get("version") == "1.2.0"]
    if not readers:
        print("No published 1.2.0 reading to check.")
        return
    issue = max(readers, key=lambda item: item["date"])
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        raise RuntimeError("A Chrome or Chromium installation is required for the Pages browser check.")
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        shutil.copyfile(ROOT / "_site" / issue["relativePath"], folder / "reading.html")
        shutil.copyfile(ROOT / "scripts" / "reader_browser.html", folder / "check.html")
        handler = functools.partial(SimpleHTTPRequestHandler, directory=folder)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run([
                chrome, "--headless", "--disable-gpu", "--disable-dev-shm-usage",
                "--user-data-dir=" + str(folder / "profile"), "--virtual-time-budget=8000", "--dump-dom",
                f"http://127.0.0.1:{server.server_port}/check.html",
            ], capture_output=True, text=True, encoding="utf-8", timeout=75, check=True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        from html.parser import HTMLParser

        class BrowserResult(HTMLParser):
            title = ""
            in_title = False

            def handle_starttag(self, tag, attrs):
                if tag == "title":
                    self.in_title = True

            def handle_endtag(self, tag):
                if tag == "title":
                    self.in_title = False

            def handle_data(self, data):
                if self.in_title:
                    self.title += data

        report = BrowserResult()
        report.feed(result.stdout)
        print(issue["relativePath"], report.title)
        if not report.title.startswith("{") or not json.loads(report.title).get("passed"):
            raise RuntimeError("Reader did not pass the mobile and desktop browser checks.")


if __name__ == "__main__":
    main()
