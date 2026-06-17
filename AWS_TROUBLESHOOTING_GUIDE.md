# AWS EC2 Troubleshooting & Maintenance Guide

This document records the exact steps, errors, and solutions encountered while deploying and maintaining the Python backend on the AWS EC2 Ubuntu server. 

If you encounter issues during `pip install` or server restarts in the future, refer to this guide!

---

## 1. Error: `[Errno 28] No space left on device`

**The Problem:**
When deploying AI models (like SBERT or PyTorch), the server's hard drive (often 8GB on AWS free tier) can instantly fill up to 100%. If `pip install` crashes midway, it leaves behind massive hidden temporary folders that permanently eat your disk space.

**The Solution (Aggressive Cleanup):**
Run these exact commands to safely reclaim gigabytes of disk space:

```bash
# 1. Delete the useless pip cache
rm -rf ~/.cache/pip

# 2. Delete corrupted/failed pip upgrade folders (folders starting with `~` in site-packages)
rm -rf ~/.local/lib/python3.14/site-packages/~*

# 3. Nuke useless GPU/NVIDIA drivers (Only if running a CPU server)
rm -rf ~/.local/lib/python3.14/site-packages/nvidia*
rm -rf ~/.local/lib/python3.14/site-packages/triton*

# 4. Safely wipe massive system text logs
sudo truncate -s 0 /var/log/syslog
sudo truncate -s 0 /var/log/auth.log
sudo rm -rf /var/log/*.gz

# 5. Clean Ubuntu's package manager cache
sudo apt-get clean
sudo apt-get autoremove -y
```

---

## 2. Error: `Defaulting to user installation...` or Packages Not Found by Server

**The Problem:**
You successfully run `sudo pip3 install my_package`, but when you look at the backend logs using `sudo journalctl -u nco-backend`, it says `ERROR: my_package is not installed`. 

Why? Because your `nco-backend` service (Gunicorn) is running inside an isolated **Python Virtual Environment (`venv`)**. If you run `pip install` globally or using `sudo` without activating the virtual environment, the server literally cannot see the package!

**The Solution:**
Always activate the virtual environment *before* installing anything!

```bash
# 1. Go to your project folder
cd /var/www/nco-backend

# 2. Activate the virtual environment
source venv/bin/activate
# (You should see "(venv)" appear in your terminal prompt)

# 3. Install the package
pip install your_package_name

# 4. Restart the server
sudo systemctl restart nco-backend
```

---

## 3. The Danger of `pip install -r requirements.txt`

**The Problem:**
You add one tiny package (like `deep-translator` which is 42 KB) to your `requirements.txt` file. You run `pip install -r requirements.txt`. Suddenly, pip starts downloading 800 Megabytes of updates for `pandas`, `scipy`, and `transformers`, completely crashing your server's hard drive!

Why? Because if your `requirements.txt` doesn't have exact version numbers (e.g. `pandas==1.5.0`), `pip` will attempt to upgrade *every single package* to its newest version.

**The Solution:**
If your server is already running perfectly and you just want to add one new package, **do not** run `pip install -r requirements.txt`. 

Instead, install the specific package directly into the virtual environment:
```bash
source venv/bin/activate
pip install deep-translator
```

---

## 4. Error: `externally-managed-environment` (PEP 668)

**The Problem:**
On newer versions of Ubuntu (like 24.04+), running `pip install` outside of a virtual environment will throw a massive red error saying `This environment is externally managed`. This is an OS protection to prevent you from breaking core system python files.

**The Solution:**
The absolute best solution is to use a virtual environment (see Section 2). 
However, if you absolutely must install something globally on a dedicated app server, you can bypass the block by appending a special flag:

```bash
pip3 install my_package --break-system-packages
```
