import os, time, json, urllib.parse, datetime, csv, tempfile, smtplib
import streamlit as st
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from resume_parser import extract_text, extract_keywords
from rapidfuzz.fuzz import partial_ratio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

APP_PASSWORD = "yourapppass"  # 🔐 Set your desired app password here

# ------------------ LinkedIn Automation ------------------
def get_driver():
    options = uc.ChromeOptions()
    driver = uc.Chrome(version_main=137, options=options)
    driver.implicitly_wait(5)
    driver.safe_quit = lambda: driver.quit()
    return driver

def login(driver, email, password):
    driver.get("https://www.linkedin.com/login")
    driver.find_element(By.ID, "username").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password + Keys.RETURN)
    WebDriverWait(driver, 15).until(EC.url_contains("/feed"))

def extract_job_links(driver, pages):
    links = set()
    page = 1
    while page <= pages:
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a[href*="/jobs/view/"]'))
            )
            job_cards = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/jobs/view/"]')
            for card in job_cards:
                url = card.get_attribute("href")
                if url and "/jobs/view/" in url and url not in links:
                    links.add(url)
        except:
            break
        if page == pages:
            break
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            pagination_buttons = driver.find_elements(By.XPATH, '//button[contains(@aria-label, "Page")]')
            if len(pagination_buttons) < page + 1:
                break
            next_button = pagination_buttons[page]
            if next_button.is_displayed() and next_button.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_button)
                WebDriverWait(driver, 10).until(EC.staleness_of(job_cards[0]))
                time.sleep(2)
                page += 1
            else:
                break
        except:
            break
    return list(links)

def fetch_descriptions(driver, links, batch_size=5):
    descriptions = []
    for i in range(0, len(links), batch_size):
        batch = links[i:i + batch_size]
        for url in batch:
            driver.execute_script(f"window.open('{url}', '_blank');")
            time.sleep(1)
        handles = driver.window_handles
        for j, url in enumerate(batch):
            try:
                driver.switch_to.window(handles[j + 1])
                WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                text = driver.find_element(By.TAG_NAME, "body").text.lower()
                descriptions.append((url, text))
            except:
                descriptions.append((url, ""))
        for h in handles[1:]:
            driver.switch_to.window(h)
            driver.close()
        driver.switch_to.window(handles[0])
    return descriptions

def match_jobs(resume_name, job_links, resume_skills):
    matched = []
    timestamp = datetime.datetime.now().isoformat()
    csv_path = f"data/matched_jobs_{resume_name}.csv"
    json_path = f"data/matched_jobs_{resume_name}.json"
    os.makedirs("data", exist_ok=True)

    existing = set()
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            existing = {row["url"] for row in csv.DictReader(f)}

    driver = get_driver()
    results = fetch_descriptions(driver, job_links)
    driver.safe_quit()

    for url, desc in results:
        if not desc or url in existing or not resume_skills:
            continue
        score = round(sum(partial_ratio(skill.lower(), desc) for skill in resume_skills) / len(resume_skills) / 100, 2)
        if score >= 0.4:
            matched.append({
                "url": url,
                "score": score,
                "description": desc[:300].replace("\n", " "),
                "timestamp": timestamp
            })

    with open(csv_path, "a", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "score", "description", "timestamp"])
        if os.stat(csv_path).st_size == 0:
            writer.writeheader()
        for job in matched:
            if job["url"] not in existing:
                writer.writerow(job)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([j for j in matched if j["url"] not in existing], f, indent=2)

    return matched

def send_email(to_email, matched_count):
    sender_email = "youremail@gmail.com"
    sender_pass = "your-app-password"
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = "✅ Job Matching Completed"

    body = f"Hi,\n\nYour resume job matching process has completed.\nMatched Jobs: {matched_count}\n\nThanks!"
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, sender_pass)
    server.send_message(msg)
    server.quit()

# ------------------ Streamlit App ------------------
st.set_page_config(page_title="🔐 Resume Job Matcher", layout="wide")
st.title("🔐 Resume Matcher - Protected App")

# 🔐 Password protection (fixed with st.rerun)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("🔑 Enter App Password", type="password")
    if pwd == APP_PASSWORD:
        st.success("✅ Access Granted. Loading...")
        st.session_state.authenticated = True
        st.rerun()
    elif pwd:
        st.error("❌ Incorrect password")
    st.stop()

# Main form
with st.form("main_form"):
    email = st.text_input("📧 LinkedIn Email")
    password = st.text_input("🔒 LinkedIn Password", type="password")
    location = st.text_input("📍 Job Location", value="India")
    notify_email = st.text_input("📬 Notify me at (email, optional)")
    pages = st.number_input("📄 Pages to Scrape", min_value=1, max_value=10, value=2)
    resumes = st.file_uploader("📁 Upload Resume(s)", type=["pdf", "txt", "docx"], accept_multiple_files=True)
    submitted = st.form_submit_button("🚀 Start Matching")

if submitted:
    if not resumes:
        st.error("❌ Upload at least one resume.")
        st.stop()

    for uploaded_file in resumes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp:
            temp.write(uploaded_file.read())
            resume_path = temp.name
            resume_name = uploaded_file.name.split('.')[0].replace(" ", "_")

        text = extract_text(resume_path)
        skills = extract_keywords(text)
        if not skills:
            st.error(f"❌ No skills extracted from {uploaded_file.name}. Try a better-formatted resume.")
            continue

        st.success(f"🧠 Skills: {', '.join(skills)}")

        try:
            driver = get_driver()
            login(driver, email, password)
        except Exception as e:
            st.error("❌ LinkedIn login failed.")
            continue

        query = urllib.parse.quote_plus(" ".join(skills))
        loc = urllib.parse.quote_plus(location)
        driver.get(f"https://www.linkedin.com/jobs/search/?keywords={query}&location={loc}&f_TPR=r86400")
        time.sleep(3)

        job_links = extract_job_links(driver, pages)
        driver.safe_quit()

        st.info(f"🔗 Found {len(job_links)} job links.")
        matched = match_jobs(resume_name, job_links, skills)
        st.success(f"✅ {len(matched)} matched jobs saved.")

        if matched:
            st.dataframe(matched)
            st.download_button("📥 Download CSV", data=open(f"data/matched_jobs_{resume_name}.csv", "rb").read(),
                               file_name=f"matched_jobs_{resume_name}.csv")

        if notify_email:
            send_email(notify_email, len(matched))
            st.info(f"📧 Notification sent to {notify_email}.")
