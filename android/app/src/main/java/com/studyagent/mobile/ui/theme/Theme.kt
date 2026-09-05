package com.studyagent.mobile.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val Ink = Color(0xFF102B3F)
val Mist = Color(0xFFF4F7F9)
val Paper = Color(0xFFFFFFFF)
val CourseBlue = Color(0xFF3561F4)
val ExamCoral = Color(0xFFE05A4F)
val StudyTeal = Color(0xFF138A81)
val Quiet = Color(0xFF667985)
val Line = Color(0xFFDCE5EA)
val SkyWash = Color(0xFFEAF0FF)
val TealWash = Color(0xFFE4F4F1)
val CoralWash = Color(0xFFFFECE9)

private val LightColors = lightColorScheme(
    primary = CourseBlue,
    onPrimary = Color.White,
    primaryContainer = SkyWash,
    onPrimaryContainer = Ink,
    secondary = StudyTeal,
    onSecondary = Color.White,
    secondaryContainer = TealWash,
    onSecondaryContainer = Ink,
    error = ExamCoral,
    onError = Color.White,
    background = Mist,
    onBackground = Ink,
    surface = Paper,
    onSurface = Ink,
    surfaceVariant = Color(0xFFEDF2F5),
    onSurfaceVariant = Quiet,
    outline = Line,
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF9BB8FF),
    onPrimary = Color(0xFF092458),
    secondary = Color(0xFF80D3CC),
    onSecondary = Color(0xFF003734),
    error = Color(0xFFFFB4AA),
    background = Color(0xFF0E1B24),
    onBackground = Color(0xFFE6EEF2),
    surface = Color(0xFF142631),
    onSurface = Color(0xFFE6EEF2),
    surfaceVariant = Color(0xFF203641),
    onSurfaceVariant = Color(0xFFB8C6CE),
    outline = Color(0xFF455C68),
)

private val AppTypography = Typography(
    headlineSmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.ExtraBold,
        fontSize = 23.sp,
        lineHeight = 29.sp,
        letterSpacing = (-0.4).sp,
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 19.sp,
        lineHeight = 25.sp,
        letterSpacing = (-0.15).sp,
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 15.sp,
        lineHeight = 21.sp,
    ),
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 14.sp, lineHeight = 20.sp),
    labelLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 13.sp,
        lineHeight = 18.sp,
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        lineHeight = 15.sp,
    ),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(22.dp),
)

@Composable
fun StudyAgentTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}
