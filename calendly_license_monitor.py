"""
Script: calendly_license_monitor - Monitor Calendly License Usage and Send Alerts

Description:
This script monitors Calendly license usage by fetching all organization members using the Calendly API
and cross-referencing with the Calendly-Users group in Okta. It calculates license usage, 
checks against the total allocated licenses, and sends alerts to a Slack channel.

Functions:
- fetch_calendly_users: Fetches Calendly organization members.
- fetch_okta_group_members: Fetches members of the Calendly-Users group in Okta.
- calculate_license_counts: Calculates license usage based on matching Calendly and Okta data.
- post_to_slack: Sends a message to a Slack channel via webhook.
- main: Main function to perform calculations and send alerts.

Usage:
1. Set the following environment variables:
   - `CALENDLY_API_TOKEN`: Calendly API token with org member access.
   - `CALENDLY_ORG_URL`: Calendly Organization URL.
   - `OKTA_API_TOKEN`: Okta API token with group member access.
   - `OKTA_BASE_URL`: Okta API base URL.
   - `OKTA_CALENDLY_GROUP_ID`: Okta Group ID for Calendly users.
   - `SLACK_WEBHOOK_URL`: Webhook URL for Slack alerts.
2. Run the script in a Python environment or via GitHub Actions.

Notes:
- Ensure the API tokens, URLs, and group ID are valid and have sufficient permissions.
- Adjust the `TOTAL_LICENSES` variable to reflect your organization's license allocation.

Author: Chad Ramey
Date: December 18, 2024
"""

import os
import requests

# Total allocated licenses
TOTAL_LICENSES = 65

def fetch_calendly_users(calendly_token, calendly_org_url):
    """Fetch all users in the Calendly organization."""
    headers = {"Authorization": f"Bearer {calendly_token}", "Content-Type": "application/json"}
    users = []
    url = f"https://api.calendly.com/organization_memberships?organization={calendly_org_url}"

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        users.extend(data.get("collection", []))
        url = data.get("pagination", {}).get("next_page")
    
    return {u["user"]["email"].lower() for u in users}

def fetch_okta_group_members(okta_token, okta_base_url, group_id):
    """Fetch all users in the specified Okta group."""
    headers = {"Authorization": f"SSWS {okta_token}", "Accept": "application/json"}
    users = {}
    url = f"{okta_base_url}/groups/{group_id}/users"

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        for user in data:
            # Include both ACTIVE and SUSPENDED users
            email = user["profile"]["email"].lower()
            users[email] = user
        url = response.links.get("next", {}).get("url")  # Handle pagination
    
    return set(users.keys())

def calculate_license_counts(calendly_users, okta_users):
    """Calculate license usage based on matched users."""
    matched_users = calendly_users.intersection(okta_users)
    licenses_used = len(matched_users)
    licenses_available = TOTAL_LICENSES - licenses_used
    return {
        "total_licenses": TOTAL_LICENSES,
        "licenses_used": licenses_used,
        "licenses_available": licenses_available
    }

def post_to_slack(webhook_url, message):
    """Send a message to Slack via webhook."""
    payload = {"text": message}
    response = requests.post(webhook_url, json=payload)
    response.raise_for_status()

def main():
    """Main function to monitor Calendly licenses and send Slack alerts."""
    # Environment variables
    calendly_token = os.getenv("CALENDLY_API_TOKEN")
    calendly_org_url = os.getenv("CALENDLY_ORG_URL")
    okta_token = os.getenv("OKTA_API_TOKEN")
    okta_base_url = os.getenv("OKTA_BASE_URL")
    group_id = os.getenv("OKTA_CALENDLY_GROUP_ID")
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not all([calendly_token, calendly_org_url, okta_token, okta_base_url, group_id, slack_webhook_url]):
        raise ValueError("Missing required environment variables.")

    # Fetch Calendly and Okta users
    print("Fetching Calendly users...")
    calendly_users = fetch_calendly_users(calendly_token, calendly_org_url)

    print("Fetching Okta group members...")
    okta_users = fetch_okta_group_members(okta_token, okta_base_url, group_id)

    # Calculate license counts
    print("Calculating license counts...")
    license_counts = calculate_license_counts(calendly_users, okta_users)

    # Generate Slack message
    if license_counts["licenses_used"] > TOTAL_LICENSES:
        alert_message = (
            f":rotating_light:calendly: *Calendly License Alert* :calendly::rotating_light:\n"
            f"Used Licenses: {license_counts['licenses_used']}\n"
            f"Total Licenses: {license_counts['total_licenses']}\n"
            f"Overage: {license_counts['licenses_used'] - TOTAL_LICENSES}\n"
            f"*Immediate action required to resolve the overage.*"
        )
    else:
        alert_message = (
            f":calendly: *Calendly License Report* :calendly:\n"
            f"Used Licenses: {license_counts['licenses_used']}\n"
            f"Total Licenses: {license_counts['total_licenses']}\n"
            f"Available Licenses: {license_counts['licenses_available']}\n"
            f"*All licenses are within the allocated limit.*"
        )

    # Send message to Slack
    print("Sending alert to Slack...")
    post_to_slack(slack_webhook_url, alert_message)

if __name__ == "__main__":
    main()
