# scraper.py

import requests
from bs4 import BeautifulSoup

def scrape_remote_co():
    """
    This function scrapes job postings from remote.co's developer section.
    It returns a list of jobs, where each job is a dictionary.
    """
    URL = "https://remote.co/remote-jobs/developer/"
    print(f"Scraping jobs from: {URL}")

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
        response = requests.get(URL, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        jobs_list = []
        job_table = soup.find('table', class_='job_listings')
        
        if not job_table:
            print("Could not find the job listings table.")
            return []

        job_rows = job_table.find_all('tr', class_='job_listing')[1:]
        print(f"Found {len(job_rows)} jobs.")

        for job_row in job_rows:
            title_element = job_row.find('td', class_='job_title').find('a')
            company_element = job_row.find('td', class_='company')

            if title_element and company_element:
                title = title_element.text.strip()
                link = "https://remote.co" + title_element['href']
                company = company_element.text.strip()
                job_data = {
                    "title": title,
                    "company": company,
                    "link": link
                }
                jobs_list.append(job_data)

        return jobs_list

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during scraping: {e}")
        return []

