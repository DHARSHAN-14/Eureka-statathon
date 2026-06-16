# Flutter App Network & Configuration Guide

## 🎯 Where to Connect

Your Flutter app needs to know where your Flask backend is running.

### Option 1: Android Emulator (DEFAULT ✅)

**Already configured! No changes needed.**

- **URL:** `http://10.0.2.2:5000`
- **Why:** `10.0.2.2` is the emulator's address for your local machine
- **Prerequisites:**
  - Flask backend running on `http://127.0.0.1:5000`
  - Android emulator started
  - Network connectivity between emulator and host

**To verify it works:**
```bash
# In Android emulator browser, visit:
http://10.0.2.2:5000
# Should show your Flask app homepage
```

---

### Option 2: Physical Android Device (WiFi)

**Requires configuration change:**

#### Step 1: Find Your Computer's IP Address

**Windows:**
```bash
ipconfig
```
Look for "IPv4 Address" under your active network adapter. Usually looks like:
- `192.168.x.x` (home WiFi)
- `10.x.x.x` (corporate WiFi)

**macOS/Linux:**
```bash
ifconfig
# or
ip addr show
```

#### Step 2: Update Flutter App

Edit: `lib/services/api_service.dart`

Find this line:
```dart
static const String baseUrl = 'http://10.0.2.2:5000'; // For Android emulator
```

Replace with your IP (example):
```dart
static const String baseUrl = 'http://192.168.1.100:5000'; // Your actual IP
```

#### Step 3: Verify Connection

On your phone's browser, visit:
```
http://192.168.1.100:5000
```

Should show your Flask app.

#### Step 4: Run App
```bash
flutter run
```

**Common mistakes:**
- ❌ Using `localhost` or `127.0.0.1` - won't work on phone
- ❌ Including port in IP when finding it (`192.168.1.100:5000`) - just `192.168.1.100`
- ❌ Using old IP if you switch networks - IP can change!
- ✅ Same network required - phone must be on same WiFi as computer

---

### Option 3: Production / Deployed Backend

If your backend is deployed to a server:

Edit: `lib/services/api_service.dart`

```dart
static const String baseUrl = 'https://your-domain.com'; // Use HTTPS!
```

**Important:** Use HTTPS for production!

---

## 🔐 Network Permissions

### Android Manifest (Already Added)

The app automatically has these permissions in `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

No manual changes needed.

---

## 🚨 Troubleshooting Connection Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| "Connection refused" | Backend not running | Start Flask: `python app.py` |
| "Connection timeout" | Wrong IP address | Verify IP with `ipconfig` |
| "Host unreachable" | Not on same network | Connect phone to same WiFi |
| "Name resolution failed" | DNS issue | Use IP instead of domain name |
| Emulator can't reach backend | Backend on wrong interface | Ensure `0.0.0.0:5000` or `127.0.0.1:5000` |

### Debug Network Connection

**Test backend directly from phone/emulator:**

1. Open Chrome on device
2. Type: `http://10.0.2.2:5000` (emulator) OR `http://192.168.x.x:5000` (phone)
3. Should see Flask app homepage
4. If it works here, it'll work in the Flutter app

**Check backend logs:**

```bash
# Terminal where Flask is running
# You should see:
# POST /api/search - 200  [timestamp]
# When you search in the app
```

---

## 🔄 Changing Configuration

The app URL is **only** in one place:

**File:** `lib/services/api_service.dart`

**Line:** `static const String baseUrl = ...`

After changing:
1. Save file
2. Run: `flutter run` or press `R` in console (hot reload)

---

## 📋 Configuration Checklist

- [ ] Flask backend is running on port 5000
- [ ] Android emulator is started (or device connected)
- [ ] Correct URL in `lib/services/api_service.dart`
- [ ] Can access backend from device browser
- [ ] Network connectivity confirmed
- [ ] `flutter pub get` has been run

---

## 💾 Quick Reference

### Copy-Paste URLs

**Android Emulator (default):**
```
http://10.0.2.2:5000
```

**Common Home Network IP:**
```
http://192.168.1.100:5000
```

**Corporate Network IP:**
```
http://10.0.1.50:5000
```

**Localhost (won't work on phone):**
```
http://localhost:5000  ❌
http://127.0.0.1:5000  ❌
```

---

## 🆘 Still Not Working?

### Checklist
1. ✅ Flask running? (`python app.py` shows "Running on..."?)
2. ✅ Emulator/device has network? (Can open websites in browser?)
3. ✅ Correct URL? (Can visit it from device browser?)
4. ✅ Port correct? (Flask on 5000, not 3000 or 8000?)
5. ✅ Hot reloaded app? (Pressed R or restarted?)

### Nuclear Option
```bash
# Stop everything
# Terminal 1: Stop Flask (Ctrl+C)
# Terminal 2: Stop Flutter (q)
# Android Studio: Stop emulator

# Start fresh
# 1. Start emulator
# 2. python app.py
# 3. flutter run
```

---

**Need more help? Check SETUP_GUIDE.md or PROJECT_SUMMARY.md**
