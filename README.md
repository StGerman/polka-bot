# Polka Bot

A Telegram bot that validates URLs and posts them to a channel under the channel’s name. Polka Bot supports `/help`, `/stop` commands, logs in detail, and can notify an admin on errors. It’s built with Python 3.12+, FastAPI, and python-telegram-bot, following Python community best practices.

## Table of Contents
1. [Project Overview](#project-overview)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Docker](#docker)
7. [Testing](#testing)
8. [Docs](#docs)
9. [GitHub Actions](#github-actions)
10. [License](#license)

---

## Project Overview

Polka Bot listens for Telegram webhook updates and:

- Validates user-submitted URLs via HEAD requests.
- Posts valid URLs to a specified public channel.
- Supports `/help` (instructions) and `/stop` (unsubscribe from bot replies).
- Provides detailed logging and optional admin notifications if something goes wrong.

---

## Requirements

- **Python** >= 3.12
- **Poetry** >= 1.5.0
- **Telegram Bot Token** (Bot must be admin in your desired public channel)
- **Docker** (optional, for containerized deployment if desired)

---

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/polka-bot.git
   cd polka-bot
