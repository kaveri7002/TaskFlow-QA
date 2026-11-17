import uuid

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


@pytest.mark.selenium
def test_registration_login_task_search_edit_delete_and_logout(selenium_driver, live_server):
    driver = selenium_driver
    unique = uuid.uuid4().hex[:8]
    email = f"selenium-{unique}@example.com"
    task_title = f"Verify release {unique}"
    driver.get(live_server)
    wait = WebDriverWait(driver, 10)

    driver.find_element(By.CSS_SELECTOR, '[data-mode="register"]').click()
    driver.find_element(By.NAME, "name").send_keys("Selenium Tester")
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "password").send_keys("SeleniumPass123")
    driver.find_element(By.CSS_SELECTOR, "#auth-form button[type=submit]").click()
    wait.until(EC.presence_of_element_located((By.ID, "new-task")))

    driver.find_element(By.ID, "new-task").click()
    dialog = driver.find_element(By.ID, "task-dialog")
    dialog.find_element(By.NAME, "title").send_keys(task_title)
    dialog.find_element(By.NAME, "description").send_keys("Created by Selenium.")
    dialog.find_element(By.NAME, "priority").send_keys("High")
    dialog.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".task-card")))

    search = driver.find_element(By.ID, "search")
    search.send_keys(task_title)
    wait.until(EC.text_to_be_present_in_element((By.CLASS_NAME, "task-card"), task_title))
    card = driver.find_element(By.CSS_SELECTOR, ".task-card")
    card.find_element(By.CSS_SELECTOR, "[data-edit]").click()
    edit_dialog = driver.find_element(By.ID, "task-dialog")
    title = edit_dialog.find_element(By.NAME, "title")
    title.clear()
    title.send_keys(f"{task_title} edited")
    edit_dialog.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    wait.until(EC.text_to_be_present_in_element((By.CLASS_NAME, "task-card"), "edited"))

    driver.find_element(By.ID, "search").clear()
    driver.find_element(By.CSS_SELECTOR, ".task-card [data-delete]").click()
    driver.switch_to.alert.accept()
    wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".task-card")))

    driver.find_element(By.ID, "logout").click()
    wait.until(EC.presence_of_element_located((By.ID, "auth-form")))
    assert "Sign in to your space" in driver.page_source


@pytest.mark.selenium
def test_invalid_login_displays_helpful_error(selenium_driver, live_server):
    driver = selenium_driver
    driver.get(live_server)
    driver.find_element(By.NAME, "email").send_keys("missing@example.com")
    driver.find_element(By.NAME, "password").send_keys("IncorrectPass123")
    driver.find_element(By.CSS_SELECTOR, "#auth-form button[type=submit]").click()
    message = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".form-message"))
    )
    assert "incorrect" in message.text.lower()
