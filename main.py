"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json. Set TOTALJOBS_PROXY first (see config.py).
"""
import json
import os

from totaljobs import companies, jobs, refs

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # a job id or any totaljobs.com job link
    save("job_108161697.json", jobs.details(refs.resolve_job("108161697")))

    # 25 jobs per page, with every site filter
    save("search_software_engineer_london.json", jobs.search(keyword="software engineer", location="London"))

    # an employer's profile: a name, a company id or a company link
    save("company_apple.json", companies.details(refs.resolve_company("apple")))
