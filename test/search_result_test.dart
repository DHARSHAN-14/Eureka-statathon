import 'package:flutter_test/flutter_test.dart';
import 'package:nco_search_app/models/search_result.dart';

void main() {
  group('SearchResult JSON Parsing Tests', () {
    test('Should parse simple search result JSON format successfully', () {
      final json = {
        'occupation_title': 'Software Developer',
        'nco_code': '2512.0100',
        'nco_2004': '2131.20',
        'division': 'Information Technology',
        'sub_division': 'Software Development',
        'group': 'Developers',
        'family': 'Systems',
        'occupation_description': 'Designs and develops computer software systems.',
        'score': 0.95,
      };

      final result = SearchResult.fromJson(json);

      expect(result.occupationalTitle, 'Software Developer');
      expect(result.nco2015, '2512.0100');
      expect(result.nco2004, '2131.20');
      expect(result.division, 'Information Technology');
      expect(result.subDivision, 'Software Development');
      expect(result.group, 'Developers');
      expect(result.family, 'Systems');
      expect(result.occupationDescription, 'Designs and develops computer software systems.');
      expect(result.score, 0.95);
    });

    test('Should parse nested details object from API response successfully', () {
      final json = {
        'occupation_title': 'Medical Doctor',
        'nco_2015': '2211.0100',
        'final_score': 0.88,
        'details': {
          'nco_2004_code': '2221.10',
          'division': 'Health Professionals',
          'sub_division': 'Medical Doctors',
          'group': 'General Practitioners',
          'family': 'General Medicine',
          'occupation_description': 'Diagnoses and treats illnesses.',
        }
      };

      final result = SearchResult.fromJson(json);

      expect(result.occupationalTitle, 'Medical Doctor');
      expect(result.nco2015, '2211.0100');
      expect(result.nco2004, '2221.10');
      expect(result.division, 'Health Professionals');
      expect(result.subDivision, 'Medical Doctors');
      expect(result.group, 'General Practitioners');
      expect(result.family, 'General Medicine');
      expect(result.occupationDescription, 'Diagnoses and treats illnesses.');
      expect(result.score, 0.88);
    });

    test('Should handle null values and fallback to N/A default values', () {
      final json = {
        'occupation_title': null,
        'nco_code': null,
      };

      final result = SearchResult.fromJson(json);

      expect(result.occupationalTitle, 'N/A');
      expect(result.nco2015, 'N/A');
      expect(result.nco2004, isNull);
      expect(result.division, 'N/A');
      expect(result.subDivision, 'N/A');
      expect(result.group, 'N/A');
      expect(result.family, 'N/A');
      expect(result.occupationDescription, 'N/A');
      expect(result.score, isNull);
    });
  });
}
