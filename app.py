import streamlit as st
import os
import time
import json
import urllib.parse
from datetime import datetime
from resume_parser import extract_text, extract_keywords
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from rapidfuzz.fuzz import partial_ratio
from tqdm import tqdm

MATCH_THRESHOLD = 0.7

# Setup Selenium
def get_driver():
    options = Options()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)

# Wait until logged in manually
def wait_for_login(driver):
    driver.get("https://www.linkedin.com/login")
    st.info("🔐 Please log in to LinkedIn manually in the opened browser window...")
    try:
        WebDriverWait(driver, 300).until(EC.url_contains("/feed"))
        st.success("✅ Logged in to LinkedIn successfully!")
    except TimeoutException:
        st.error("❌ Login timeout. Please restart the app and try again.")

# Extract job links from current search page
def extract_job_links(driver, pages):
    links = set()
    for page in range(pages):
        st.info(f"🔍 Scanning page {page + 1}...")
        time.sleep(3)
        jobs = driver.find_elements(By.CSS_SELECTOR, "a.job-card-list__title")
        for job in jobs:
            url = job.get_attribute("href")
            if url:
                links.add(url.split("?")[0])
        try:
            next_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Page ' + str(page + 2) + '"]'))
            )
            driver.execute_script("arguments[0].click();", next_btn)
        except:
            break
    return list(links)

# Get job description text
def get_job_description(driver, url):
    try:
        driver.get(url)
        time.sleep(2)
        jd = driver.find_element(By.CLASS_NAME, "jobs-description-content__text").text
        return jd
    except:
        return ""

# Match JD with skills
def match_skills(jd, skills):
    matches = [skill for skill in skills if partial_ratio(skill.lower(), jd.lower()) > 80]
    return len(matches) / len(skills)

# Main App
st.set_page_config(page_title="Job Matcher", layout="wide")
st.title("🔎 Resume-Based Job Matcher")

password = st.text_input("🔐 Enter app password", type="password")
if password != "letmein":
    st.stop()

resume_file = st.file_uploader("📄 Upload Resume (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"])
location = st.text_input("📍 Enter job location (e.g. India, US, Remote)")
pages = st.number_input("📄 Number of job result pages to scan", min_value=1, max_value=10, value=2)
start = st.button("🚀 Start Job Matching")

if start and resume_file and location:
    resume_text = extract_text(resume_file)
    skills = extract_keywords(resume_text)
    if not skills:
        st.error("❌ No skills found in resume. Try uploading a better-formatted resume.")
        st.stop()

    st.success(f"🧠 Extracted Skills: {', '.join(skills)}")
    driver = get_driver()
    wait_for_login(driver)

    st.info("📣 Please perform your job search manually on LinkedIn, then click 'Continue'.")
    if st.button("✅ Continue after search"):
        links = extract_job_links(driver, pages)
        st.success(f"🔗 Found {len(links)} job links.")

        matched = []
        for link in tqdm(links, desc="📥 Matching jobs"):
            jd = get_job_description(driver, link)
            score = match_skills(jd, skills)
            if score >= MATCH_THRESHOLD:
                matched.append({"url": link, "score": round(score, 2), "date": str(datetime.now())})

        if matched:
            os.makedirs("data", exist_ok=True)
            output_path = f"data/matched_jobs_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("url,score,date\n")
                for job in matched:
                    f.write(f"{job['url']},{job['score']},{job['date']}\n")
            st.success(f"✅ Saved {len(matched)} matched jobs to `{output_path}`.")
        else:
            st.warning("⚠️ No matched jobs found.")

        driver.quit()
