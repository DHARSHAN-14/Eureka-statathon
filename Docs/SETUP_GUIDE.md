# NCO Occupation Search - Flutter App

A Flutter mobile application for searching National Classification of Occupations (NCO) using semantic search powered by your Flask backend.

## Features

✅ **Semantic Search** - Find occupations using natural language job descriptions
✅ **NCO Code Lookup** - Direct search by NCO 2015 or 2004 codes
✅ **Clean Form-like UI** - Survey-style search form with expandable results
✅ **Real-time Results** - Display match scores and detailed occupation information
✅ **Customizable Results** - Choose how many results to display (top-k)
✅ **Error Handling** - Graceful error messages and connection management

## Architecture

```
lib/
├── main.dart              # App entry point
├── models/
│   └── search_result.dart # Data model for search results
├── services/
│   └── api_service.dart   # Backend API integration
└── screens/
    └── search_screen.dart # Main search UI with form and results
```

## Getting Started

### Prerequisites

- Flutter SDK (3.12.1+)
- Android emulator or physical device
- Your Flask backend running (see setup below)

### Installation

1. **Clone/Navigate to the app:**
   ```bash
   cd nco_search_app
   ```

2. **Get dependencies:**
   ```bash
   flutter pub get
   ```

3. **Update Backend URL** (if not localhost):
   - Edit `lib/services/api_service.dart`
   - Change `baseUrl` constant to match your backend URL
   - For Android emulator: `http://10.0.2.2:5000` (default)
   - For physical device: `http://<your-machine-ip>:5000`

### Running the App

**Android Emulator:**
```bash
flutter run
```

**Physical Android Device:**
1. Enable USB debugging on device
2. Connect via USB
3. Run: `flutter run`

**iOS:**
```bash
flutter run -d ios
```

## Backend Setup

Ensure your Flask backend is running and accessible:

```bash
# Set database URL
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/statathon_nco

# Install dependencies
pip install -r requirements.txt

# Run migration (first time only)
python scripts/migrate_to_postgres.py

# Start server
python app.py
```

Server will run on `http://127.0.0.1:5000` by default.

## Network Configuration

### For Android Emulator
The app uses `http://10.0.2.2:5000` by default, which is a special alias for `localhost` on the emulator.

### For Physical Device
Update `lib/services/api_service.dart`:
```dart
static const String baseUrl = 'http://192.168.x.x:5000'; // Replace with your machine IP
```

To find your machine IP:
```bash
# Windows
ipconfig
# macOS/Linux
ifconfig
```

### For Production/Deployed Backend
Update the URL in `api_service.dart`:
```dart
static const String baseUrl = 'https://your-domain.com'; // Use HTTPS for production
```

**Note:** For HTTPS connections, you may need to configure certificate pinning.

## Using the App

### 1. Search Mode Selection
- **Semantic**: Natural language search (e.g., "software developer", "teacher")
- **NCO Code**: Exact code lookup (e.g., "2211.0100")

### 2. Enter Search Query
- For semantic: Describe the occupation
- For NCO code: Enter the full NCO code

### 3. Set Result Count
- Default: 10 results
- Adjustable: 1-100 recommended

### 4. View Results
- **Expandable Cards**: Click to see full details
- **Match Score**: Semantic search shows confidence percentage
- **Hierarchy Info**: Division, Sub-division, Group, Family
- **Description**: Full occupation description

## API Integration

The app connects to your Flask backend `/api/search` endpoint:

**Request:**
```json
{
  "query": "software engineer",
  "top_k": 10,
  "search_mode": "general"
}
```

**Response:**
```json
{
  "results": [
    {
      "occupational_title": "Software Developer",
      "nco_2015": "2211.0100",
      "nco_2004": "2211",
      "division": "Professionals",
      "sub_division": "...",
      "group": "...",
      "family": "...",
      "occupation_description": "...",
      "score": 0.95
    }
  ]
}
```

## Troubleshooting

### Connection Error
- **Check backend URL** in `api_service.dart`
- **Verify backend is running** on correct port
- **Network access**: Enable network permissions in Android manifest

### No Results
- Check your search query syntax
- Verify database migration completed on backend
- Check backend logs for errors

### Android Emulator Network Issues
- Ensure `http://10.0.2.2:5000` is used (not `localhost`)
- Restart emulator if connection hangs
- Check Android Network Settings

### Physical Device Connection
- Ensure device and machine are on same network
- Update URL to your machine's IP address
- Disable firewall if necessary

## Building for Release

### Android APK
```bash
flutter build apk --release
```

### Android App Bundle (for Play Store)
```bash
flutter build appbundle --release
```

### iOS
```bash
flutter build ios --release
```

Built artifacts will be in `build/` directory.

## Project Structure

- **models/** - Data classes representing API responses
- **services/** - HTTP client and API integration
- **screens/** - UI screens (search form and results display)
- **main.dart** - App initialization and theming

## Customization

### Theme Colors
Edit `main.dart`:
```dart
colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
```

### Form Fields
Edit `screens/search_screen.dart` to add/modify:
- Language selection
- Advanced filters
- Custom result display

### API Response Parsing
Update `models/search_result.dart` if backend response format changes.

## Known Limitations

- Currently supports HTTP/HTTPS only (no WebSocket)
- No offline caching (requires backend connection)
- No multi-language translation UI (backend supports translation via `/api/translate`)

## Future Enhancements

- [ ] Add search history/favorites
- [ ] Implement offline caching with Hive
- [ ] Add voice input integration
- [ ] Multi-language UI support
- [ ] Advanced filters (division, family, etc.)
- [ ] Result sharing functionality
- [ ] Dark mode support

## Dependencies

- **http** - HTTP client for API calls
- **flutter** - Flutter framework
- **cupertino_icons** - iOS-style icons

## License

Part of Eureka Statathon project.

## Support

For issues or questions:
1. Check backend logs: `python app.py`
2. Verify network connectivity
3. Check API response format in browser: `http://localhost:5000/api/search`
4. Review error messages in app

---

**Happy searching! 🔍**
