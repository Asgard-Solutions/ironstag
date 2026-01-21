/**
 * Expo Config Plugin: Android Colors Resource Fix
 * 
 * This plugin ensures that required color resources are defined
 * in the Android colors.xml file to prevent release build failures.
 * 
 * Error this fixes:
 * error: resource color/activityBackground not found
 * Execution failed for task ':app:processReleaseResources'
 * 
 * The release build enforces strict resource validation and fails when
 * theme references point to undefined colors.
 */

const { withAndroidColors } = require('@expo/config-plugins');

/**
 * Add required color resources to colors.xml
 */
function withActivityBackgroundColor(config) {
  return withAndroidColors(config, (config) => {
    // Ensure resources object exists
    if (!config.modResults.resources) {
      config.modResults.resources = {};
    }
    
    // Get existing colors or initialize empty array
    const colors = config.modResults.resources.color || [];
    
    // Define required colors that may be referenced by themes
    const requiredColors = [
      { name: 'activityBackground', value: '#1a1a1a' },
      { name: 'colorPrimaryDark', value: '#1a1a1a' },
      { name: 'splashscreen_background', value: '#0E1A14' },
    ];
    
    requiredColors.forEach(({ name, value }) => {
      const exists = colors.some((color) => color.$?.name === name);
      
      if (!exists) {
        colors.push({
          $: { name },
          _: value,
        });
        console.log(`[android-colors-plugin] Added ${name} color resource: ${value}`);
      }
    });
    
    // Ensure colors array is set back
    config.modResults.resources.color = colors;
    
    return config;
  });
}

module.exports = withActivityBackgroundColor;
