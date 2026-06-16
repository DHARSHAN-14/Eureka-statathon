# Flutter App Quick Start

## ⚡ 5-Minute Setup

### Step 1: Backend Ready?
Ensure your Flask backend is running:
```bash
cd d:\The Project\statathon1.1.worktrees\agents-project-overview-documentation
python app.py
```
It should say: `Running on http://127.0.0.1:5000/`

### Step 2: Open Flutter Project
```bash
cd d:\The Project\statathon1.1.worktrees\nco_search_app
```

### Step 3: Start Android Emulator
- Open Android Studio
- Launch your Android Virtual Device (AVD)
- Wait until it fully loads (you'll see home screen)

### Step 4: Run Flutter App
```bash
flutter run
```

This will:
1. Compile your Flutter code
2. Install the app on the emulator
3. Launch it automatically

**First run takes ~2-5 minutes. Subsequent runs are faster.**

### Step 5: Use the App
1. Open app (should appear on emulator)
2. Enter a job description in the search field
3. Tap "Search"
4. Results appear below in expandable cards
5. Tap any result to see full details

---

## 🔌 Network Configuration

### Android Emulator (Default - No Changes Needed!)
The app is pre-configured to connect to `http://10.0.2.2:5000`

**If it doesn't work:**
- Make sure Flask backend is running on port 5000
- Check Android Studio > Device Manager > Emulator running?
- Restart emulator: Device Manager > Stop > Start

### Physical Android Device
**Change backend URL:**
1. Find your computer's IP:
   ```bash
   ipconfig  # Windows
   # Look for "IPv4 Address" in your network adapter
   ```

2. Edit `lib/services/api_service.dart`:
   ```dart
   static const String baseUrl = 'http://192.168.X.X:5000'; // Your IP here
   ```

3. Save file and run:
   ```bash
   flutter run
   ```

---

## 📱 Hot Reload (Pro Tip!)

After first run, changes are instant:
```bash
# In the running app console, press 'r' to hot reload
r    # Hot reload (keeps app state)
R    # Hot restart (resets app)
q    # Quit
```

---

## 🐛 Debugging

### Check Emulator Network
```bash
# In emulator, open Chrome and visit:
http://10.0.2.2:5000
# Should show your Flask app homepage
```

### Check Backend
```bash
# In terminal where Flask is running, you should see:
# POST /api/search - when you search in app
```

### View App Logs
```bash
# Flutter console shows app output
# Look for errors like "Connection refused"
```

---

## 🚀 Advanced: Physical Device via USB

1. **Enable USB Debugging:**
   - Settings > About Phone > Tap Build Number 7 times
   - Settings > Developer Options > Enable USB Debugging
   - Connect via USB cable

2. **Run on device:**
   ```bash
   flutter run
   ```

3. **Your computer IP must be accessible:**
   - Same WiFi network OR
   - USB connection (Android can reach computer directly)

---

## 📦 Building for Installation

**To create an APK to install on any Android phone:**
```bash
flutter build apk --release
```

APK will be at: `build/app/outputs/flutter-app.apk`

Transfer to phone and tap to install (enable unknown sources first).

---

## 💡 Pro Tips

1. **Keep backend terminal visible** - See requests in real-time
2. **Use emulator's clipboard** - Paste long NCO codes easily
3. **Test both search modes**:
   - "Semantic": Software developer
   - "NCO Code": 2211.0100
4. **Check match scores** - Higher % = better match

---

## ⚠️ Common Issues

| Issue | Fix |
|-------|-----|
| "Connection refused" | Flask backend not running? |
| App won't start | Run `flutter pub get` again |
| Emulator too slow | Use more CPU cores: Device Mgr > Settings |
| Results empty | Check query isn't blank; wait for search |
| "Wrong IP error" | Confirm IP format `192.168.x.x` not `192.168.x.x:5000` |

---

## 📚 Learn More

Full documentation: See `SETUP_GUIDE.md` in project root

---

**Ready? Start Flutter app and search! 🎉**
