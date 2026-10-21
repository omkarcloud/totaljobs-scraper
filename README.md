# 💼 Totaljobs Scraper

Totaljobs Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Totaljobs data for free.

## ✨ What Can I Get?

- 🔍 **Search 130K+ live UK jobs** — salary, employer, location & posting date, with every Totaljobs filter
- 📄 **Full job details** — every section, salary range, hybrid flag, exact coordinates & employer rating
- 🏢 **Employer profiles** — Apple, Morgan Stanley, Tesco & co: logo, live job count, where and what they hire
- 📊 **Market stats & 250+ career guides** — live job counts by type, remote, skill & place, plus Totaljobs' job descriptions

## 🎥 Example: A Full Totaljobs Job

```json
{
  "id": 108161697,
  "title": "Lead Software Engineer - Equities - VP",
  "link": "https://www.totaljobs.com/job/lead-software-engineer-equities-vp/morgan-stanley-job108161697",
  "posted_at": "2026-10-13T18:29:04Z",
  "expires_at": "2026-11-24T19:29:04Z",
  "contract_type": "Permanent Contract; Hybrid",
  "remote": "partial",
  "industry": "IT, IT-Software Development",
  "location": { "text": "London", "latitude": 51.500145, "longitude": -0.12623 },
  "description": {
    "text": "We’re seeking someone to join our team as aaJava developer to work on automated trading systems, primarily in the Equities domain. ..."
  },
  "company": {
    "id": 1387034,
    "name": "Morgan Stanley",
    "logo_link": "https://tjgliveassets.s3.eu-west-1.amazonaws.com/company-logos/436930a9b51548358ea28e934c86483d.png",
    "rating": { "average": 3.86, "count": 570 },
    "sectors": ["Other Business Activities & Services"]
  },
  "similar_jobs": [
    {
      "id": 108209535,
      "title": "Senior Software Engineer",
      "company": { "id": 404866, "name": "Understanding Recruitment" },
      "location": { "text": "City of London (EC1), EC1" },
      "salary": { "text": "£150000 - £200000 per annum", "min": 150000, "max": 200000, "currency": "GBP", "period": "year" }
    }
  ]
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Totaljobs Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/totaljobs-scraper
cd totaljobs-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

Totaljobs sits behind Akamai, which turns away datacenter IPs. If your calls come back as "blocked the request", point the scraper at a UK residential proxy and start it again:
```bash
export TOTALJOBS_PROXY="http://user:pass@host:port"
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/jobs/details?job=108161697"
```

```json
{
  "id": 108161697,
  "title": "Lead Software Engineer - Equities - VP",
  "link": "https://www.totaljobs.com/job/lead-software-engineer-equities-vp/morgan-stanley-job108161697",
  "posted_at": "2026-10-13T18:29:04Z",
  "expires_at": "2026-11-24T19:29:04Z",
  "employment_type": "FULL_TIME",
  "contract_type": "Permanent Contract; Hybrid",
  "remote": "partial",
  "industry": "IT, IT-Software Development",
  "location": { "text": "London", "latitude": 51.500145, "longitude": -0.12623 },
  "company": {
    "id": 1387034,
    "name": "Morgan Stanley",
    "rating": { "average": 3.86, "count": 570 }
  }
}
```

All 14 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

14 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Job Details | `/jobs/details` | Every section, salary, hybrid flag, coordinates, employer rating and similar jobs |
| Search Jobs | `/jobs/search` | 25 UK jobs per page with salary, employer and every site filter |
| Jobs by IDs | `/jobs/batch` | Up to 10 full job ads in one call |
| Company Details | `/companies/details` | Any employer by name: logo, live job count, agency or direct |
| Company Jobs | `/companies/jobs` | Every live job at one employer, filterable, 25 per page |
| Similar Jobs | `/jobs/similar` | The 10 jobs Totaljobs recommends next to any job |
| Job Market Stats | `/jobs/stats` | Live job counts by posting age, type, remote, skill and place |
| Search Filters | `/jobs/filters` | Every filter option with live job counts for your search |
| Jobs by Search Link | `/jobs/by-link` | The jobs behind any Totaljobs search or company URL |
| Autocomplete | `/autocomplete` | Totaljobs' own job-title suggestions with live job counts |
| Popular Searches | `/searches/popular` | Trending searches and the busiest nearby locations for any place |
| Career Article Details | `/advice/details` | A full career article: sections, FAQs, author and related reads |
| Career Articles by Topic | `/advice/articles` | 250+ job descriptions and career guides, browsed by topic |
| Search Career Advice | `/advice/search` | Search Totaljobs' career advice library, 10 articles per page |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-totaljobs-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-totaljobs-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-totaljobs-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/jobs/search",
    params={"keyword": "software engineer", "location": "London", "job_type": "permanent", "remote": "full"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Totaljobs Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20Totaljobs%20Scraper%20API.)

[![Ask Us by Email about Totaljobs Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Totaljobs%20Scraper%20API&body=I%20need%20help%20using%20the%20Totaljobs%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**Reed Scraper**](https://github.com/omkarcloud/reed-scraper) — Reed.co.uk UK jobs, salaries, employers & application counts
- [**Stepstone Scraper**](https://github.com/omkarcloud/stepstone-scraper) — Stepstone jobs, salaries & employer profiles from 8 European boards
- [**Glassdoor Scraper**](https://github.com/omkarcloud/glassdoor-scraper) — Glassdoor jobs, company ratings, salaries & reviews
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/totaljobs-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/totaljobs-scraper)
