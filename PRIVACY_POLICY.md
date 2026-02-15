# Privacy Policy

**Last updated:** February 14, 2026

## Overview

Tamafuji Reservation Checker ("the Service") is a personal notification tool that monitors restaurant reservation availability on TableCheck and sends SMS alerts to opted-in users. This Privacy Policy describes how we collect, use, and protect your information.

## Information We Collect

### Phone Number
We collect your phone number in E.164 format (e.g., +18081234567) when you opt in to receive SMS notifications. This is required to deliver availability alerts.

### Reservation Preferences
We collect your preferred dates, party size, and optional time preferences to determine which availability alerts are relevant to you.

### Message Logs
We retain records of notifications sent to your phone number for deduplication purposes, ensuring you are not alerted multiple times for the same availability.

## How We Use Your Information

We use your information solely to:

- Monitor TableCheck for reservation availability matching your preferences
- Send SMS notifications when matching slots become available
- Prevent duplicate notifications for the same availability

We do **not** use your information for marketing, advertising, or any purpose unrelated to reservation availability notifications.

## Data Storage

Your data is stored in AWS DynamoDB in the us-west-2 region. Data is protected by AWS security controls including encryption at rest and in transit.

## Data Retention

- **Watch preferences**: Retained while your watch is active. Deleted when you remove your watch.
- **Notification logs**: Retained for deduplication purposes and automatically expire via TTL.

## Data Sharing

We do **not** sell, rent, or share your personal information with third parties. Your phone number is shared only with Twilio for the sole purpose of delivering SMS messages to you.

## Third-Party Services

The Service uses the following third-party services:

- **AWS (Amazon Web Services)**: Cloud infrastructure and data storage
- **Twilio**: SMS message delivery
- **TableCheck**: Restaurant reservation availability data (public)

## Opt-In and Opt-Out

- **Opt-in**: You opt in by creating a watch with your phone number through the Service.
- **Opt-out**: You may opt out at any time by replying STOP to any SMS message, or by deleting your watch through the Service. We will promptly cease sending messages and delete your data.

## SMS Messaging Terms

- Message frequency varies based on reservation availability (typically a few messages per week at most).
- Message and data rates may apply depending on your carrier and plan.
- SMS is used exclusively for reservation availability alerts.

## Security

We implement reasonable security measures to protect your information, including encrypted data transmission (HTTPS/TLS), encrypted storage, and access controls.

## Changes to This Policy

We may update this Privacy Policy from time to time. Any changes will be reflected by updating the "Last updated" date above.

## Contact

If you have questions about this Privacy Policy, please contact us by opening an issue on the project's GitHub repository.
