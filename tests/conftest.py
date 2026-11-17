import os
import re
import socket
import threading
import time
import uuid
import warnings
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from backend.app import create_app, db


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    database_file = tmp_path_factory.mktemp("taskflow") / "tests.sqlite"
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "SQLALCHEMY_DATABASE_URI": os.getenv("DATABASE_URL") or f"sqlite:///{database_file.as_posix()}",
        "FRONTEND_DIST_DIR": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend")),
    })
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def isolate_test_database(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield


@pytest.fixture
def auth_headers(client):
    unique = uuid.uuid4().hex[:8]
    response = client.post("/api/auth/register", json={
        "name": "Test User",
        "email": f"test-{unique}@example.com",
        "password": "CorrectHorse9",
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json['token']}"}


@pytest.fixture(scope="session")
def live_server(app):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    else:
        server.shutdown()
        raise RuntimeError("The test web server did not start.")
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def selenium_driver():
    from selenium import webdriver
    from selenium.webdriver.common.selenium_manager import SeleniumManager

    options = webdriver.ChromeOptions()
    browser_path = SeleniumManager().binary_paths(["--browser", "chrome"]).get("browser_path")
    if browser_path:
        options.binary_location = browser_path
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1000")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    yield driver
    driver.quit()


def pytest_generate_tests(metafunc):
    if "browser_name" in metafunc.fixturenames:
        browser_names = os.getenv("TASKFLOW_BROWSERS", "chromium").split(",")
        metafunc.parametrize("browser_name", [name.strip() for name in browser_names if name.strip()])


@pytest.fixture
def playwright_page(browser_name, live_server):
    from playwright.sync_api import Error as PlaywrightError, sync_playwright

    with sync_playwright() as playwright:
        browser_type = getattr(playwright, browser_name)
        try:
            browser = browser_type.launch(headless=True)
        except PlaywrightError as error:
            if "Host system is missing dependencies!" in str(error):
                pytest.skip(f"{browser_name} is unavailable because this system is missing its Playwright browser libraries.")
            raise
        context = browser.new_context(viewport={"width": 1365, "height": 900})
        page = context.new_page()
        page.goto(live_server, wait_until="domcontentloaded")
        yield page
        context.close()
        browser.close()


@pytest.fixture
def playwright_request(live_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        request = playwright.request.new_context(base_url=live_server)
        yield request
        request.dispose()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return

    screenshot_dir = Path(__file__).resolve().parents[1] / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", item.nodeid).strip("-")
    screenshot_path = screenshot_dir / f"failed-{safe_name}.png"
    try:
        if "selenium_driver" in item.funcargs:
            item.funcargs["selenium_driver"].save_screenshot(str(screenshot_path))
        elif "playwright_page" in item.funcargs:
            item.funcargs["playwright_page"].screenshot(path=str(screenshot_path), full_page=True)
        else:
            return
        warnings.warn(f"Failure screenshot saved to {screenshot_path}", RuntimeWarning)
    except Exception as exc:
        warnings.warn(f"Could not save failure screenshot: {exc}", RuntimeWarning)
