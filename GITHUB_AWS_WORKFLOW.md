# GitHub to AWS EC2 Deployment Workflow

This guide provides a deep, step-by-step explanation of the 1-click update workflow between your local Windows machine, your GitHub repository, and your live AWS EC2 server.

---

## Phase 1: Pushing Local Changes to GitHub (From Windows)

Whenever you make changes to your Python code (`app.py`), HTML templates, or CSS files locally, you need to push those changes up to GitHub.

### Step 1: Open Your Terminal
Open a terminal in your project directory (`D:\The Project\statathon1.1`). You can use Git Bash, PowerShell, or the VS Code integrated terminal.

### Step 2: Check Modified Files
It's a good practice to see what files were modified before you commit them.
```bash
git status
```
*You will see modified files in red.*

### Step 3: Stage the Files
"Staging" tells Git which files you want to include in your next snapshot.
```bash
# To stage everything that was changed, run:
git add .
```

### Step 4: Commit the Changes
A commit wraps your staged files into a version history snapshot and attaches a descriptive message.
```bash
git commit -m "Update NCO mobile UI and clean up directory"
```
*Be descriptive so you know what changed when you look back later.*

### Step 5: Push to GitHub
Finally, push your local commits to your remote GitHub repository on the specific branch you are working on (e.g., `Kabhilan`).
```bash
git push origin Kabhilan
```
*Your code is now safely backed up on GitHub!*

---

## Phase 2: One-Time Server Setup (AWS EC2)

Because using a Personal Access Token (PAT) can be tricky and expire unexpectedly, the most robust and professional way to securely link your server to GitHub is by generating a specific "Deploy Key" for the server itself using SSH. You only need to do this **once**.

### Step 1: Initialize Git and Generate SSH Key
Log into your AWS EC2 instance. Ensure you are in the project folder, initialize a clean Git repository, and generate an SSH key:
```bash
cd /var/www/nco-backend

# Initialize an empty git repository
git init

# Generate a highly secure SSH key
ssh-keygen -t ed25519 -C "ubuntu@ec2"
```
*(When prompted where to save the key or to enter a passphrase, just **press the Enter key 3 times** to accept all the default settings).*

### Step 2: Retrieve Your Public Key
Print the newly generated public key to the screen:
```bash
cat ~/.ssh/id_ed25519.pub
```
*(Copy the entire output line that starts with `ssh-ed25519 ...`)*

### Step 3: Add the Key to GitHub
1. Go to your GitHub repository in the web browser (**DHARSHAN-14/Eureka-statathon**).
2. Click on **Settings** (the tab at the top).
3. On the left sidebar menu, click **Deploy keys**.
4. Click the **Add deploy key** button.
5. In the **Title** field, type `AWS EC2 Server`.
6. In the **Key** field, paste the copied SSH key.
7. Click **Add key**.

---

## Phase 3: Linking and Pulling Updates (AWS EC2)

Now that GitHub recognizes your server's SSH key, you can link the repository and pull your code effortlessly.

### Step 1: Link the Repository
Run this command in your EC2 terminal to tell the server where to pull code from using the SSH protocol:
```bash
cd /var/www/nco-backend

git remote add origin git@github.com:DHARSHAN-14/Eureka-statathon.git
```

### Step 2: Fetch and Switch Branch
Download the information from GitHub and force the server to switch to your working branch:
```bash
# Fetch all branch updates from GitHub
git fetch origin

# Force checkout the 'Kabhilan' branch
git checkout -f Kabhilan
```

### Step 3: Pull Latest Code
If you are already on the branch and just want to download the newest commits you pushed from Windows:
```bash
git pull origin Kabhilan
```

### Step 4: Install Python Dependencies (If Changed)
If your latest pull includes changes to `requirements.txt` (like adding new packages), install them using pip. **Crucially**, make sure to activate your virtual environment so the packages are installed where your web server can see them!
```bash
# Activate the virtual environment
source venv/bin/activate

# Install the dependencies
pip install -r requirements.txt
```

### Step 5: Restart the Flask Backend
For your new code to take effect (especially Python backend code changes in `app.py`), you must restart the system daemon that runs your web app.
```bash
sudo systemctl restart nco-backend
```

---

## Summary: Your Future 2-Step Update Routine
Once Phase 2 and Phase 3 are set up, updating your app in the future takes just seconds!

**1. On Windows:**
```bash
git add .
git commit -m "Describe updates"
git push origin Kabhilan
```

**2. On AWS EC2:**
```bash
cd /var/www/nco-backend
git pull origin Kabhilan

# (Only run the next two lines if you added new packages to requirements.txt)
source venv/bin/activate
pip install -r requirements.txt

sudo systemctl restart nco-backend
```
