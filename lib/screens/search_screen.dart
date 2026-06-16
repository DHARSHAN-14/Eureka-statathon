import 'package:flutter/material.dart';
import 'dart:math';
import '../models/search_result.dart';
import '../services/api_service.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TextEditingController _queryController = TextEditingController();
  final TextEditingController _topKController = TextEditingController(text: '10');

  List<SearchResult> _results = [];
  bool _isLoading = false;
  String? _error;
  String _searchMode = 'general';

  @override
  void dispose() {
    _queryController.dispose();
    _topKController.dispose();
    super.dispose();
  }

  Future<void> _performSearch() async {
    if (_queryController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a search query')),
      );
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
      _results = [];
    });

    try {
      final topK = int.tryParse(_topKController.text) ?? 10;
      final results = await ApiService.search(
        query: _queryController.text,
        topK: topK,
        searchMode: _searchMode,
      );

      setState(() {
        _results = results;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
        _isLoading = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $_error')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    const Color ashokaBluePrimary = Color(0xFF1F3C6F);
    const Color indiaOrange = Color(0xFFFF9933);

    return Scaffold(
      appBar: AppBar(
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Government of India',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                letterSpacing: 0.5,
                color: Colors.white,
              ),
            ),
            Text(
              'National Classification of Occupations',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ],
        ),
        leading: Padding(
          padding: const EdgeInsets.all(8.0),
          child: Container(
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
            ),
            child: Center(
              child: CustomPaint(
                size: const Size(40, 40),
                painter: _AshokaChakraPainter(color: const Color(0xFF1F3C6F)),
              ),
            ),
          ),
        ),
        elevation: 2,
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header Section
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: ashokaBluePrimary.withOpacity(0.05),
                  border: Border(
                    left: BorderSide(
                      color: indiaOrange,
                      width: 4,
                    ),
                  ),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  'Search for occupations by job description or NCO code',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: ashokaBluePrimary,
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Search Mode Selection
              _buildSectionCard(
                title: 'Search Mode',
                child: Row(
                  children: [
                    Expanded(
                      child: _buildRadioTile(
                        title: 'Job Description',
                        subtitle: 'Semantic search',
                        value: 'general',
                      ),
                    ),
                    Expanded(
                      child: _buildRadioTile(
                        title: 'NCO Code',
                        subtitle: 'Direct lookup',
                        value: 'nco',
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Search Query Field
              _buildSectionCard(
                title: 'Enter Search Query',
                child: TextField(
                  controller: _queryController,
                  decoration: InputDecoration(
                    hintText: _searchMode == 'nco'
                        ? 'Example: 2211.0100'
                        : 'Example: Software developer, Teacher',
                    hintStyle: TextStyle(
                      color: Colors.grey.shade400,
                      fontSize: 13,
                    ),
                    prefixIcon: const Icon(Icons.search),
                  ),
                  maxLines: 3,
                  minLines: 1,
                  style: const TextStyle(fontSize: 15),
                ),
              ),
              const SizedBox(height: 16),

              // Results Count
              _buildSectionCard(
                title: 'Number of Results',
                child: TextField(
                  controller: _topKController,
                  decoration: InputDecoration(
                    hintText: 'Default: 10 (Max: 100)',
                    prefixIcon: const Icon(Icons.format_list_numbered),
                  ),
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(height: 24),

              // Search Button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _isLoading ? null : _performSearch,
                  icon: _isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor:
                                AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Icon(Icons.search),
                  label: Text(
                    _isLoading ? 'Searching...' : 'Search',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.5,
                    ),
                  ),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(6),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 32),

              // Results Section
              if (_results.isNotEmpty)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4.0),
                      child: Text(
                        'Search Results (${_results.length} found)',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: ashokaBluePrimary,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    ListView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: _results.length,
                      itemBuilder: (context, index) {
                        final result = _results[index];
                        return ResultCard(result: result, index: index);
                      },
                    ),
                  ],
                ),

              if (_isLoading)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(32.0),
                    child: CircularProgressIndicator(),
                  ),
                ),

              if (_error != null && !_isLoading)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    border: Border.all(
                      color: Colors.red.shade300,
                      width: 1,
                    ),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.error_outline,
                        color: Colors.red.shade700,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _error!,
                          style: TextStyle(
                            color: Colors.red.shade900,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

              if (_results.isEmpty && !_isLoading && _error == null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 64.0),
                  child: Center(
                    child: Column(
                      children: [
                        Icon(
                          Icons.search,
                          size: 56,
                          color: Colors.grey.shade300,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Enter a search query to begin',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w500,
                            color: Colors.grey.shade600,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Search by occupation name or NCO code',
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.grey.shade500,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required Widget child,
  }) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Color(0xFF1F3C6F),
                letterSpacing: 0.3,
              ),
            ),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }

  Widget _buildRadioTile({
    required String title,
    required String subtitle,
    required String value,
  }) {
    final isSelected = _searchMode == value;
    return GestureDetector(
      onTap: () {
        setState(() => _searchMode = value);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF1F3C6F).withOpacity(0.08) : null,
          border: Border.all(
            color: isSelected ? const Color(0xFF1F3C6F) : Colors.grey.shade300,
            width: isSelected ? 2 : 1,
          ),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Row(
          children: [
            Radio<String>(
              value: value,
              groupValue: _searchMode,
              onChanged: (val) {
                if (val != null) {
                  setState(() => _searchMode = val);
                }
              },
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ResultCard extends StatelessWidget {
  final SearchResult result;
  final int index;

  const ResultCard({
    super.key,
    required this.result,
    required this.index,
  });

  @override
  Widget build(BuildContext context) {
    const Color ashokaBluePrimary = Color(0xFF1F3C6F);
    const Color indiaOrange = Color(0xFFFF9933);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${index + 1}. ${result.occupationalTitle}',
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 15,
                color: ashokaBluePrimary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              result.nco2015,
              style: const TextStyle(
                color: indiaOrange,
                fontWeight: FontWeight.w500,
                fontSize: 12,
                letterSpacing: 0.3,
              ),
            ),
          ],
        ),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: double.infinity,
                  height: 1,
                  color: Colors.grey.shade200,
                  margin: const EdgeInsets.only(bottom: 16),
                ),
                _buildInfoRow('NCO 2015', result.nco2015),
                if (result.nco2004 != null && result.nco2004!.isNotEmpty)
                  _buildInfoRow('NCO 2004', result.nco2004!),
                _buildHierarchyRow('Division', result.division),
                _buildHierarchyRow('Sub-Division', result.subDivision),
                _buildHierarchyRow('Group', result.group),
                _buildHierarchyRow('Family', result.family),
                const SizedBox(height: 12),
                const Divider(height: 1),
                const SizedBox(height: 12),
                const Text(
                  'Occupation Description:',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                    color: ashokaBluePrimary,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  result.occupationDescription,
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: Colors.grey.shade800,
                  ),
                ),
                if (result.score != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: ashokaBluePrimary.withOpacity(0.05),
                      border: Border(
                        left: BorderSide(
                          color: indiaOrange,
                          width: 3,
                        ),
                      ),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Match Score:',
                          style: TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                            color: ashokaBluePrimary,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: indiaOrange.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: indiaOrange.withOpacity(0.4),
                            ),
                          ),
                          child: Text(
                            '${(result.score! * 100).toStringAsFixed(1)}%',
                            style: const TextStyle(
                              color: indiaOrange,
                              fontWeight: FontWeight.bold,
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 8),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    const Color ashokaBluePrimary = Color(0xFF1F3C6F);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              '$label:',
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 12,
                color: ashokaBluePrimary,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade800,
                fontFamily: 'Courier',
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHierarchyRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              '$label:',
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 12,
                color: Color(0xFF1F3C6F),
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Custom painter for Ashoka Chakra (simplified spokes)
class _AshokaChakraPainter extends CustomPainter {
  final Color color;

  _AshokaChakraPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;

    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 3;

    // Draw circle
    canvas.drawCircle(center, radius, paint);

    // Draw 12 spokes (simplified for visibility)
    for (int i = 0; i < 12; i++) {
      final angle = (i * 30) * (pi / 180); // 30 degrees apart
      final x1 = center.dx + (radius - 6) * cos(angle);
      final y1 = center.dy + (radius - 6) * sin(angle);
      final x2 = center.dx + radius * cos(angle);
      final y2 = center.dy + radius * sin(angle);
      canvas.drawLine(Offset(x1, y1), Offset(x2, y2), paint);
    }

    // Draw center dot
    canvas.drawCircle(center, 2, paint..style = PaintingStyle.fill);
  }

  @override
  bool shouldRepaint(_AshokaChakraPainter oldDelegate) => false;
}
