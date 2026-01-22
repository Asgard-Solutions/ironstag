/**
 * Expo Config Plugin: Android 15/16 MainActivity Enhancements
 * 
 * This plugin modifies MainActivity.kt to add:
 * 1. Modern edge-to-edge setup using WindowCompat and WindowInsetsController
 * 2. onConfigurationChanged handler for orientation changes
 * 3. onMultiWindowModeChanged handler for split-screen/foldable support
 * 
 * This addresses Android 15 deprecation warnings for:
 * - Window.setStatusBarColor / getStatusBarColor
 * - Window.setNavigationBarColor / getNavigationBarColor
 * - LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES / DEFAULT
 * 
 * The new approach uses WindowInsetsController for system bar styling.
 */

const { withMainActivity } = require('@expo/config-plugins');

/**
 * Required imports for modern edge-to-edge implementation
 */
const REQUIRED_IMPORTS = [
  'import android.content.res.Configuration',
  'import android.os.Build',
  'import android.os.Bundle',
  'import android.view.View',
  'import android.view.WindowManager',
  'import androidx.core.view.WindowCompat',
  'import androidx.core.view.WindowInsetsControllerCompat',
];

/**
 * Add required imports if not present
 */
function addRequiredImports(contents) {
  REQUIRED_IMPORTS.forEach((importLine) => {
    if (!contents.includes(importLine)) {
      // Add after the last existing import
      const lastImportIndex = contents.lastIndexOf('import ');
      if (lastImportIndex !== -1) {
        const endOfImportLine = contents.indexOf('\n', lastImportIndex);
        contents = 
          contents.slice(0, endOfImportLine + 1) +
          importLine + '\n' +
          contents.slice(endOfImportLine + 1);
      }
    }
  });
  
  return contents;
}

/**
 * Add modern edge-to-edge setup method using Android 15 compatible APIs
 */
function addEdgeToEdgeSetup(contents) {
  const methodSignature = 'private fun setupEdgeToEdge()';
  
  if (!contents.includes(methodSignature)) {
    // Find the closing brace of the class to insert before it
    const classEndRegex = /(\n})(\s*)$/;
    
    const edgeToEdgeMethod = `
  /**
   * Modern edge-to-edge setup using Android 15+ compatible APIs.
   * Uses WindowCompat and WindowInsetsControllerCompat instead of deprecated
   * Window.setStatusBarColor/setNavigationBarColor APIs.
   */
  private fun setupEdgeToEdge() {
    val window = window ?: return
    
    // Enable edge-to-edge using the modern WindowCompat API
    WindowCompat.setDecorFitsSystemWindows(window, false)
    
    // Get the WindowInsetsController for controlling system bar appearance
    val insetsController = WindowCompat.getInsetsController(window, window.decorView)
    
    // Configure system bar appearance (light/dark icons)
    // For dark theme app: use light (white) system bar icons
    insetsController.isAppearanceLightStatusBars = false
    insetsController.isAppearanceLightNavigationBars = false
    
    // Set transparent system bars (the modern way)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
      window.isStatusBarContrastEnforced = false
      window.isNavigationBarContrastEnforced = false
    }
    
    // Handle display cutouts properly
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
      window.attributes.layoutInDisplayCutoutMode = 
        WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
    }
  }

`;
    
    contents = contents.replace(classEndRegex, edgeToEdgeMethod + '$1$2');
  }
  
  return contents;
}

/**
 * Modify onCreate to call edge-to-edge setup
 */
function modifyOnCreate(contents) {
  const setupCall = 'setupEdgeToEdge()';
  
  // Check if already added
  if (contents.includes(setupCall)) {
    return contents;
  }
  
  // Find onCreate method and add setupEdgeToEdge() call after super.onCreate
  // Handle both super.onCreate(savedInstanceState) and super.onCreate(null)
  const onCreateSuperRegex = /(super\.onCreate\([^)]*\))/g;
  
  if (onCreateSuperRegex.test(contents)) {
    contents = contents.replace(onCreateSuperRegex, `$1\n    // Setup edge-to-edge using modern Android 15+ APIs\n    setupEdgeToEdge()`);
  }
  
  return contents;
}

/**
 * Add onConfigurationChanged override if not present
 */
function addConfigurationChangedHandler(contents) {
  const methodSignature = 'override fun onConfigurationChanged';
  
  if (!contents.includes(methodSignature)) {
    // Find the closing brace of the class to insert before it
    const classEndRegex = /(\n})(\s*)$/;
    
    const configChangedMethod = `
  /**
   * Handle configuration changes (orientation, screen size, etc.)
   * This ensures edge-to-edge display is maintained during orientation changes
   * and multi-window mode transitions on tablets and foldables.
   * Added for Android 15/16 large screen compliance.
   */
  override fun onConfigurationChanged(newConfig: Configuration) {
    super.onConfigurationChanged(newConfig)
    // Re-apply edge-to-edge setup after configuration changes
    setupEdgeToEdge()
  }

`;
    
    contents = contents.replace(classEndRegex, configChangedMethod + '$1$2');
  }
  
  return contents;
}

/**
 * Add onMultiWindowModeChanged override if not present
 */
function addMultiWindowModeChangedHandler(contents) {
  const methodSignature = 'override fun onMultiWindowModeChanged';
  
  if (!contents.includes(methodSignature)) {
    // Find the closing brace of the class to insert before it
    const classEndRegex = /(\n})(\s*)$/;
    
    const multiWindowMethod = `
  /**
   * Handle multi-window mode changes (split-screen, freeform, etc.)
   * Required for Android 7.0+ multi-window support on tablets and foldables.
   * Added for Android 15/16 large screen compliance.
   */
  override fun onMultiWindowModeChanged(isInMultiWindowMode: Boolean, newConfig: Configuration) {
    super.onMultiWindowModeChanged(isInMultiWindowMode, newConfig)
    // Re-apply edge-to-edge setup when entering/exiting multi-window mode
    setupEdgeToEdge()
  }

`;
    
    contents = contents.replace(classEndRegex, multiWindowMethod + '$1$2');
  }
  
  return contents;
}

/**
 * Main function to modify MainActivity
 */
function withLargeScreenMainActivity(config) {
  return withMainActivity(config, (config) => {
    let contents = config.modResults.contents;
    
    console.log('[android-large-screen-main-activity] Modifying MainActivity.kt for Android 15/16...');
    
    // Add required imports
    contents = addRequiredImports(contents);
    
    // Add edge-to-edge setup method
    contents = addEdgeToEdgeSetup(contents);
    
    // Modify onCreate to call setup
    contents = modifyOnCreate(contents);
    
    // Add configuration change handlers
    contents = addConfigurationChangedHandler(contents);
    contents = addMultiWindowModeChangedHandler(contents);
    
    config.modResults.contents = contents;
    
    console.log('[android-large-screen-main-activity] MainActivity.kt modifications complete');
    
    return config;
  });
}

module.exports = withLargeScreenMainActivity;
