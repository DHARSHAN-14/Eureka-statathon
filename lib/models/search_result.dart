class SearchResult {
  final String occupationalTitle;
  final String nco2015;
  final String? nco2004;
  final String division;
  final String subDivision;
  final String group;
  final String family;
  final String occupationDescription;
  final double? score;

  SearchResult({
    required this.occupationalTitle,
    required this.nco2015,
    this.nco2004,
    required this.division,
    required this.subDivision,
    required this.group,
    required this.family,
    required this.occupationDescription,
    this.score,
  });

  factory SearchResult.fromJson(Map<String, dynamic> json) {
    // Handle nested details object from backend API
    final details = json['details'] as Map<String, dynamic>? ?? {};
    
    return SearchResult(
      occupationalTitle: json['occupation_title'] ?? 'N/A',
      nco2015: json['nco_code'] ?? json['nco_2015'] ?? 'N/A',
      nco2004: details['nco_2004_code'] ?? json['nco_2004'],
      division: details['division'] ?? json['division'] ?? 'N/A',
      subDivision: details['sub_division'] ?? json['sub_division'] ?? 'N/A',
      group: details['group'] ?? json['group'] ?? 'N/A',
      family: details['family'] ?? json['family'] ?? 'N/A',
      occupationDescription: details['occupation_description'] ?? json['occupation_description'] ?? 'N/A',
      score: (json['final_score'] as num?)?.toDouble() ?? (json['score'] as num?)?.toDouble(),
    );
  }
}
