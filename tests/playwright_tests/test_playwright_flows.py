import uuid

import pytest


def create_account(page):
    unique = uuid.uuid4().hex[:8]
    page.locator(".auth-tabs").get_by_role("button", name="Create account").click()
    page.get_by_label("Your name").fill("Playwright Tester")
    page.get_by_label("Email address").fill(f"playwright-{unique}@example.com")
    page.get_by_label("Password").fill("PlaywrightPass123")
    page.get_by_role("button", name="Create account").last.click()
    page.get_by_role("heading", name="Your work, in flow.").wait_for()


@pytest.mark.playwright
def test_register_create_update_search_and_drag_task(playwright_page):
    page = playwright_page
    create_account(page)
    task_title = f"Check report {uuid.uuid4().hex[:6]}"
    page.get_by_role("button", name="New task").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Task name").fill(task_title)
    dialog.get_by_label("Description").fill("Confirm the report contents.")
    dialog.get_by_label("Priority").select_option("high")
    dialog.get_by_role("button", name="Save task").click()
    card = page.get_by_role("article", name=task_title)
    card.wait_for()
    card.get_by_role("button", name=f"Edit {task_title}").click()
    page.get_by_label("Status").select_option("in_progress")
    dialog.get_by_role("button", name="Save task").click()

    card = page.locator('.board-column[data-status="in_progress"]').get_by_role("article", name=task_title)
    card.wait_for()
    target = page.get_by_role("region", name="Completed tasks")
    with page.expect_response(lambda response: response.request.method == "PATCH" and "/api/tasks/" in response.url):
        card.drag_to(target)
    page.get_by_role("region", name="Completed tasks").get_by_role("article", name=task_title).wait_for()

    page.screenshot(path="screenshots/taskflow-board.png", full_page=True)
    page.get_by_role("searchbox", name="Search tasks").fill("not a real task")
    page.get_by_text("No matching tasks").first.wait_for()


@pytest.mark.playwright
def test_validation_and_responsive_layout(playwright_page):
    page = playwright_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator(".auth-tabs").get_by_role("button", name="Create account").click()
    page.get_by_label("Your name").fill("Validation Tester")
    page.get_by_label("Email address").fill("invalid-email")
    page.get_by_label("Password").fill("short")
    assert page.get_by_label("Email address").evaluate("(element) => element.validity.valid") is False
    assert page.get_by_label("Password").evaluate("(element) => element.validity.valid") is False
    assert page.locator("body").evaluate("(element) => element.scrollWidth <= window.innerWidth")


@pytest.mark.playwright
def test_api_can_register_and_authenticate_multiple_users(playwright_request):
    request = playwright_request
    first_email = f"api-{uuid.uuid4().hex[:8]}@example.com"
    first = request.post("/api/auth/register", data={
        "name": "First Person", "email": first_email, "password": "FirstPassword123",
    })
    second = request.post("/api/auth/register", data={
        "name": "Second Person", "email": f"api-{uuid.uuid4().hex[:8]}@example.com", "password": "SecondPassword123",
    })
    assert first.status == 201
    assert second.status == 201
    first_headers = {"Authorization": f"Bearer {first.json()['token']}"}
    task = request.post("/api/tasks", headers=first_headers, data={"title": "Private QA task"})
    assert task.status == 201
    first_tasks = request.get("/api/tasks", headers=first_headers).json()["tasks"]
    second_headers = {"Authorization": f"Bearer {second.json()['token']}"}
    second_tasks = request.get("/api/tasks", headers=second_headers).json()["tasks"]
    assert len(first_tasks) == 1
    assert second_tasks == []
