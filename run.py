# run.py
import os
import subprocess
import sys
import platform
from pathlib import Path

# --- AUTO-INSTALL PYTHON IF MISSING ---
def install_python():
    system = platform.system()
    print("\nPython 3 not found. Installing automatically...")

    if system == "Darwin":  # macOS
        print("Installing Python 3 via Homebrew (recommended)...")
        try:
            subprocess.run(["brew", "--version"], check=True, capture_output=True)
        except:
            print("Installing Homebrew first...")
            subprocess.run(
                ['/bin/bash', '-c', "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"],
                check=True
            )
        subprocess.run(["brew", "install", "python@3.11"], check=True)
        python_cmd = "python3"

    elif system == "Linux":
        print("Installing Python 3 via apt (Ubuntu/Debian)...")
        subprocess.run(["sudo", "apt", "update"], check=True)
        subprocess.run(["sudo", "apt", "install", "-y", "python3", "python3-pip"], check=True)
        python_cmd = "python3"

    elif system == "Windows":
        print("Downloading Python 3 installer...")
        url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        installer = "python-installer.exe"
        subprocess.run(["curl", "-o", installer, url], check=True, shell=True)
        print("Run the installer manually and restart terminal.")
        print(f"Download saved: {os.path.abspath(installer)}")
        sys.exit(0)

    else:
        print(f"Unsupported OS: {system}")
        sys.exit(1)

    print("Python 3 installed!")
    return python_cmd

# --- CHECK PYTHON ---
def get_python_cmd():
    try:
        result = subprocess.run(["python3", "--version"], capture_output=True, text=True)
        if "Python 3" in result.stdout:
            return "python3"
    except:
        pass

    try:
        result = subprocess.run(["python", "--version"], capture_output=True, text=True)
        if "Python 3" in result.stdout:
            return "python"
    except:
        pass

    return install_python()

# --- CONFIG QUESTIONS ---
def setup_config():
    print("\n" + "="*60)
    print(" HYPERLIQUID LTC AGENT — SETUP")
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
def install_deps(python_cmd):
    print("\nInstalling dependencies...")
    try:
        subprocess.check_call([python_cmd, "-m", "pip", "install", "-r", "requirements.txt"])
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

    # Get Python command
    python_cmd = get_python_cmd()

    # Install deps
    install_deps(python_cmd)

    # Launch bot
    print("\n" + "="*60)
    print(" LAUNCHING AGENT...")
    print("="*60 + "\n")
    
    try:
        subprocess.run([python_cmd, "main.py"])
    except KeyboardInterrupt:
        print("\nAgent stopped by user. Goodbye!")
