import 'package:flutter/material.dart';

/// Matte black + gold Material 3 dark theme. No analytics.
const Color kMatteBlack = Color(0xFF0B0B0B);
const Color kSurface = Color(0xFF141414);
const Color kGold = Color(0xFFC9A227);
const Color kGoldDim = Color(0xFF8A7219);
const Color kIvory = Color(0xFFE8E0D0);

ThemeData buildAppTheme(Brightness brightness) {
  final dark = brightness == Brightness.dark;
  const lightInk = Color(0xFF1C1915);
  const lightPaper = Color(0xFFFFFDF8);
  final scheme = dark
      ? const ColorScheme.dark(
          primary: kGold,
          onPrimary: kMatteBlack,
          secondary: kGoldDim,
          onSecondary: kIvory,
          surface: kSurface,
          onSurface: kIvory,
          error: Color(0xFFB54A4A),
          onError: kIvory,
        )
      : const ColorScheme.light(
          primary: kGold,
          onPrimary: kMatteBlack,
          secondary: kGoldDim,
          onSecondary: kMatteBlack,
          surface: lightPaper,
          onSurface: lightInk,
          error: Color(0xFFB54A4A),
          onError: Color(0xFFFFFDF8),
        );
  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    focusColor: kGold,
    scaffoldBackgroundColor: dark ? kMatteBlack : const Color(0xFFF4F0E6),
    appBarTheme: AppBarTheme(
      backgroundColor: dark ? kMatteBlack : const Color(0xFFFBF8F1),
      foregroundColor: dark ? kGold : const Color(0xFF1C1915),
      elevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: dark ? kSurface : const Color(0xFFFFFDF8),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: Color(0x33C9A227)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: dark ? const Color(0xFF1A1A1A) : const Color(0xFFFFFDF8),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: kGold),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        foregroundColor: WidgetStateProperty.resolveWith((s) {
          if (s.contains(WidgetState.selected)) return kMatteBlack;
          return dark ? kIvory : const Color(0xFF1C1915);
        }),
        backgroundColor: WidgetStateProperty.resolveWith((s) {
          if (s.contains(WidgetState.selected)) return kGold;
          return dark ? kSurface : const Color(0xFFFFFDF8);
        }),
      ),
    ),
  );
}
