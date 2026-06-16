import 'package:http/http.dart' as http;
import 'dart:convert';
import '../models/search_result.dart';

class ApiService {
  // Update this to your backend URL
  static const String baseUrl = 'http://10.0.2.2:5000'; // For Android emulator

  static Future<List<SearchResult>> search({
    required String query,
    int topK = 10,
    String searchMode = 'general',
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/search'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'query': query,
          'top_k': topK,
          'search_mode': searchMode,
        }),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final jsonData = jsonDecode(response.body);
        final results = jsonData['results'] as List;
        return results
            .map((result) => SearchResult.fromJson(result))
            .toList();
      } else {
        throw Exception(
          'Failed to search: ${response.statusCode} - ${response.body}',
        );
      }
    } catch (e) {
      throw Exception('Error searching: $e');
    }
  }

  static Future<List<String>> getLanguages() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/languages'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final jsonData = jsonDecode(response.body);
        final languages = jsonData['languages'] as Map;
        return languages.keys.cast<String>().toList();
      } else {
        return ['en'];
      }
    } catch (e) {
      return ['en'];
    }
  }
}
