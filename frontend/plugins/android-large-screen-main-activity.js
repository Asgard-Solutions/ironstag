/**
 * Expo Config Plugin: Android 16 MainActivity Enhancements
 * 
 * This plugin modifies MainActivity.kt to add:
 * 1. onConfigurationChanged handler for orientation changes
 * 2. onMultiWindowModeChanged handler for split-screen/foldable support
 * 
 * These handlers ensure proper edge-to-edge display is maintained
 * during orientation changes and multi-window transitions.
 */

const { withMainActivity } = require('@expo/config-plugins');

/**
 * Add Configuration import if not present
 */
function addConfigurationImport(contents) {
  const importLine = 'import android.content.res.Configuration';
  
  if (!contents.includes(importLine)) {
    // Add after the package declaration or existing imports
    const importRegex = /(import .*\n)(?!import)/;
    const match = contents.match(importRegex);
    
    if (match) {
      // Add after the last import
      const lastImportIndex = contents.lastIndexOf('import ');
      const endOfImportLine = contents.indexOf('\n', lastImportIndex);
      contents = 
        contents.slice(0, endOfImportLine + 1) +
        importLine + '\n' +
        contents.slice(endOfImportLine + 1);
    }
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
   * Added for Android 16 large screen compliance.
   */
  override fun onConfigurationChanged(newConfig: Configuration) {
    super.onConfigurationChanged(newConfig)
    // Re-apply edge-to-edge setup after configuration changes if method exists
    try {
      val setupMethod = this::class.java.getDeclaredMethod("setupEdgeToEdge")
      setupMethod.isAccessible = true
      setupMethod.invoke(this)
    } catch (e: Exception) {
      // setupEdgeToEdge method may not exist in all configurations
    }
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
   * Added for Android 16 large screen compliance.
   */
  override fun onMultiWindowModeChanged(isInMultiWindowMode: Boolean, newConfig: Configuration) {
    super.onMultiWindowModeChanged(isInMultiWindowMode, newConfig)
    // Re-apply edge-to-edge setup when entering/exiting multi-window mode
    try {
      val setupMethod = this::class.java.getDeclaredMethod("setupEdgeToEdge")
      setupMethod.isAccessible = true
      setupMethod.invoke(this)
    } catch (e: Exception) {
      // setupEdgeToEdge method may not exist in all configurations
    }
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
    
    console.log('[android-large-screen-main-activity] Modifying MainActivity.kt...');
    
    // Add Configuration import
    contents = addConfigurationImport(contents);
    
    // Add configuration change handlers
    contents = addConfigurationChangedHandler(contents);
    contents = addMultiWindowModeChangedHandler(contents);
    
    config.modResults.contents = contents;
    
    console.log('[android-large-screen-main-activity] MainActivity.kt modifications complete');
    
    return config;
  });
}

module.exports = withLargeScreenMainActivity;
