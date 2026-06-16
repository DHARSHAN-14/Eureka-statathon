import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nco_search_app/main.dart';
import 'package:nco_search_app/screens/search_screen.dart';
import 'package:nco_search_app/screens/splash_screen.dart';

void main() {
  group('NCO Search App UI Tests', () {
    testWidgets('SplashScreen rendering smoke test', (WidgetTester tester) async {
      // Build our app and trigger a frame.
      await tester.pumpWidget(const MyApp());

      // Verify that the splash screen shows government branding and app titles.
      expect(find.text('Government of India'), findsOneWidget);
      expect(find.text('Ministry of Labour and Employment'), findsOneWidget);
      expect(find.text('National Classification of Occupations'), findsOneWidget);
      expect(find.text('Semantic Search & Occupation Lookup'), findsOneWidget);
      
      // Verify loading indicator is present
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Advance time by 3 seconds to trigger the delayed navigation timer
      await tester.pump(const Duration(milliseconds: 3000));
      
      // Settle the navigation transition and any running animations
      await tester.pumpAndSettle();
    });

    testWidgets('SearchScreen rendering test', (WidgetTester tester) async {
      // Build the SearchScreen widget.
      await tester.pumpWidget(
        const MaterialApp(
          home: SearchScreen(),
        ),
      );

      // Verify the search mode options, query headers, and search controls.
      expect(find.text('Search Mode'), findsOneWidget);
      expect(find.text('Enter Search Query'), findsOneWidget);
      expect(find.text('Number of Results'), findsOneWidget);
      expect(find.text('Search'), findsOneWidget);
      
      // Verify text fields exist
      expect(find.byType(TextField), findsNWidgets(2)); // Query input and TopK input
    });
  });
}
