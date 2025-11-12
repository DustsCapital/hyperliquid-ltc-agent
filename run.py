# run.py
import os
import subprocess
import sys
from pathlib import Path

# --- CONFIG QUESTIONS ---
def setup_config():
    print("\n" + "="*60)
    print(" HYPERLIQUID LTC BOT — SETUP")
    print("="*60 + "\n")

    wallet = input("Enter your HyperLiquid wallet address: ").strip()
    private_key = input("Enter your private key (0x...): ").strip()
    main_wallet = input("Enter main wallet (for withdraws, or press Enter for same): ").strip() or wallet
    trade_usd = input("Trade size in USD (default 10): ").strip() or "10"

    env_content = f"""HL_WALLET={wallet}
HL_PRIVATE_KEY={private_key}
MAIN_WALLET={main_wallet}
TRADE_USDT={float(trade_usd):.2f}
"""

    env_path = Path(".env")
    env_path.write_text(env_content)
    print(f"\n.env created securely!")

# --- INSTALL DEPENDENCIES ---
def install_deps():
    print("\nInstalling dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies installed!")
    except Exception as e:
        print(f"Failed to install: {e}")
        sys.exit(1)

# --- MAIN ---
if __name__ == "__main__":
    # Create saves folder
    os.makedirs("saves", exist_ok=True)

    # Setup .env if missing
    if not Path(".env").exists():
        setup_config()
    else:
        print(".env already exists — skipping setup")

    # Install deps
    install_deps()

    # Launch bot
    print("\n" + "="*60)
    print(" LAUNCHING BOT...")
    print("="*60 + "\n")
    subprocess.run([sys.executable, "main.py"])