import os, time, csv, json, datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz.fuzz import partial_ratio
import undetected_chromedriver as uc

def get_driver():
    options = uc.ChromeOptions()
    driver = uc.Chrome(version_main=137, options=options)
    driver.implicitly_wait(5)
    driver.safe_quit = lambda: driver.quit()
    return driver

def login(driver, email, password, st):
    driver.get("https://www.linkedin.com/login")
    driver.find_element(By.ID, "username").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.ID, "password").submit()
    st.info("🔐 Complete any CAPTCHA/2FA in the browser. Waiting 15 seconds...")
    time.sleep(15)

def extract_job_links(driver, pages, st):
    links = set()
    page = 1
    while page <= pages:
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2.5)
        job_cards = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/jobs/view/"]')
        for card in job_cards:
            url = card.get_attribute("href")
            if url and url not in links:
                links.add(url)
        st.write(f"📄 Page {page}: Found {len(job_cards)} jobs.")
        page += 1
        try:
            next_btn = driver.find_element(By.XPATH, '//button[@aria-label="Page ' + str(page) + '"]')
            driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(3)
        except:
            break
    return list(links)

def fetch_descriptions(driver, links):
    results = []
    for url in links:
        driver.execute_script(f"window.open('{url}', '_blank');")
        time.sleep(1)
    tabs = driver.window_handles
    for i, url in enumerate(links):
        try:
            driver.switch_to.window(tabs[i + 1])
            WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            text = driver.find_element(By.TAG_NAME, "body").text.lower()
            results.append((url, text))
        except:
            results.append((url, ""))
    for h in tabs[1:]:
        driver.switch_to.window(h)
        driver.close()
    driver.switch_to.window(tabs[0])
    return results

def match_jobs(resume_path, links, skills, st):
    name = os.path.splitext(os.path.basename(resume_path))[0].replace(" ", "_")
    csv_path = f"data/matched_jobs_{name}.csv"
    json_path = f"data/matched_jobs_{name}.json"
    matched = []
    timestamp = datetime.datetime.now().isoformat()

    driver = get_driver()
    results = fetch_descriptions(driver, links)
    driver.safe_quit()

    for url, desc in results:
        if not desc:
            continue
        score = round(sum(partial_ratio(skill.lower(), desc) for skill in skills) / len(skills) / 100, 2)
        if score >= 0.4:
            matched.append({"url": url, "score": score, "description": desc[:300], "timestamp": timestamp})

    os.makedirs("data", exist_ok=True)
    with open(csv_path, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "score", "description", "timestamp"])
        writer.writeheader()
        for job in matched:
            writer.writerow(job)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(matched, f, indent=2)

    return matched
