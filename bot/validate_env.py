import os
import sys

REQUIRED = [
    ("API_ID",     "Telegram API ID from my.telegram.org"),
    ("API_HASH",   "Telegram API Hash from my.telegram.org"),
    ("BOT_TOKEN",  "Bot token from @BotFather"),
]

RECOMMENDED = [
    ("DATABASE_URI",   "MongoDB connection string (bot runs without persistence if missing)"),
    ("LOG_CHANNEL",    "Telegram channel ID for bot logs"),
    ("AUTH_CHANNEL",   "Channel ID users must join before using the bot"),
    ("ADMINS",         "Space-separated list of admin Telegram user IDs"),
]

OPTIONAL = [
    ("DATABASE_NAME",       "MongoDB database name (default: Rajappan)"),
    ("COLLECTION_NAME",     "MongoDB collection name (default: Telegram_files)"),
    ("CHANNELS",            "Space-separated channel IDs to index files from"),
    ("AUTH_USERS",          "Space-separated user IDs that bypass restrictions"),
    ("SUPPORT_CHAT",        "Support chat username (default: backupchannek)"),
    ("SHORTLINK_URL",       "Primary shortlink domain"),
    ("SHORTLINK_API",       "Primary shortlink API key"),
    ("MOVIE_GROUP",         "Movie request group link or @username"),
    ("VERIFY_DAILY_LIMIT",  "Verifications required per day (default: 1)"),
    ("SUB_LINK",            "Subscription/premium purchase link"),
    ("PROTECT_CONTENT",     "Prevent forwarding of sent files (True/False)"),
    ("CUSTOM_FILE_CAPTION", "Custom caption for sent files"),
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def check(var):
    return bool(os.environ.get(var, "").strip())

def print_row(status_str, var, desc):
    print(f"  {status_str}  {var:<28} {desc}")

print()
print(f"{BOLD}{CYAN}{'='*60}{RESET}")
print(f"{BOLD}{CYAN}   Media Filter Bot — Environment Check{RESET}")
print(f"{BOLD}{CYAN}{'='*60}{RESET}")
print()

missing_required = []

print(f"{BOLD}Required:{RESET}")
for var, desc in REQUIRED:
    if check(var):
        print_row(f"{GREEN}✔{RESET}", var, desc)
    else:
        print_row(f"{RED}✘{RESET}", var, f"{RED}{desc}{RESET}")
        missing_required.append(var)

print()
print(f"{BOLD}Recommended:{RESET}")
for var, desc in RECOMMENDED:
    if check(var):
        print_row(f"{GREEN}✔{RESET}", var, desc)
    else:
        print_row(f"{YELLOW}–{RESET}", var, f"{YELLOW}Not set — {desc}{RESET}")

print()
print(f"{BOLD}Optional:{RESET}")
for var, desc in OPTIONAL:
    if check(var):
        print_row(f"{GREEN}✔{RESET}", var, desc)
    else:
        print_row(f" {RESET} ", var, f"Not set — {desc}")

print()
print(f"{BOLD}{CYAN}{'='*60}{RESET}")

if missing_required:
    print(f"\n{BOLD}{RED}❌  Startup aborted. The following required variables are not set:{RESET}")
    for var in missing_required:
        print(f"    • {var}")
    print(f"\n    Set them in Railway → Variables before redeploying.\n")
    sys.exit(1)

print(f"\n{BOLD}{GREEN}✅  All required variables are set. Starting bot...{RESET}\n")
