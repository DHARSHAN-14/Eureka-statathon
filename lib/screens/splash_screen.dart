import 'package:flutter/material.dart';
import 'dart:math';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeIn),
    );

    _scaleAnimation = Tween<double>(begin: 0.8, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeOutBack),
    );

    _animationController.forward();

    // Navigate to SearchScreen after animation completes
    Future.delayed(const Duration(milliseconds: 3000), () {
      if (mounted) {
        Navigator.of(context).pushReplacementNamed('/search');
      }
    });
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const Color ashokaBluePrimary = Color(0xFF1F3C6F);
    const Color indiaOrange = Color(0xFFFF9933);


    return Scaffold(
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              ashokaBluePrimary,
              Color(0xFF2D4E8C),
            ],
          ),
        ),
        child: Center(
          child: FadeTransition(
            opacity: _fadeAnimation,
            child: ScaleTransition(
              scale: _scaleAnimation,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Indian Emblem (Ashoka Chakra with Lion Capital)
                  Container(
                    width: 120,
                    height: 120,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.95),
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.3),
                          blurRadius: 20,
                          spreadRadius: 5,
                        ),
                      ],
                    ),
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        // Ashoka Chakra (outer circle)
                        Container(
                          width: 100,
                          height: 100,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: ashokaBluePrimary,
                              width: 2,
                            ),
                          ),
                        ),
                        // Ashoka Chakra (24 spokes - simplified)
                        CustomPaint(
                          size: const Size(100, 100),
                          painter: AshokaChakraPainter(
                            color: ashokaBluePrimary,
                          ),
                        ),
                        // Center dot
                        Container(
                          width: 16,
                          height: 16,
                          decoration: const BoxDecoration(
                            color: ashokaBluePrimary,
                            shape: BoxShape.circle,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 32),

                  // Government of India Text
                  const Text(
                    'Government of India',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                      letterSpacing: 1.2,
                    ),
                  ),
                  const SizedBox(height: 8),

                  // Ministry/Department
                  const Text(
                    'Ministry of Labour and Employment',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w400,
                      color: Colors.white70,
                      letterSpacing: 0.5,
                    ),
                  ),
                  const SizedBox(height: 24),

                  // App Title
                  const Text(
                    'National Classification of Occupations',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                      letterSpacing: 0.3,
                    ),
                  ),
                  const SizedBox(height: 8),

                  // Subtitle
                  const Text(
                    'Semantic Search & Occupation Lookup',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w400,
                      color: indiaOrange,
                    ),
                  ),
                  const SizedBox(height: 48),

                  // Loading Indicator
                  const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      valueColor:
                          AlwaysStoppedAnimation<Color>(Colors.white),
                      strokeWidth: 2,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// Custom painter for Ashoka Chakra
class AshokaChakraPainter extends CustomPainter {
  final Color color;

  AshokaChakraPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 2;

    // Draw 24 spokes (simplified as lines)
    for (int i = 0; i < 24; i++) {
      final angle = (i * 360 / 24) * (pi / 180);
      final x1 = center.dx + (radius - 8) * cos(angle);
      final y1 = center.dy + (radius - 8) * sin(angle);
      final x2 = center.dx + radius * cos(angle);
      final y2 = center.dy + radius * sin(angle);
      canvas.drawLine(Offset(x1, y1), Offset(x2, y2), paint);
    }

    // Draw inner circle of chakra
    canvas.drawCircle(center, radius - 15, paint);
  }

  @override
  bool shouldRepaint(AshokaChakraPainter oldDelegate) => false;
}
