import requests
import urllib.parse
import json

def get_openfda_data(drug_name):
    encoded_name = urllib.parse.quote(drug_name)
    url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:\"{encoded_name}\"&limit=1"

    print(f"Querying OpenFDA...\nURL: {url}\n")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        print("Response:\n")
        print(json.dumps(data, indent=2))  # Pretty-print the entire JSON

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error: {http_err}")
    except Exception as err:
        print(f"Unexpected error: {err}")

if __name__ == "__main__":
    drug = input("Enter drug name to inspect OpenFDA data: ").strip()
    get_openfda_data(drug)
