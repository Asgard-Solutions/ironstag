/**
 * Expo Config Plugin: Android Colors Resource Fix
 * 
 * This plugin ensures that the `activityBackground` color resource is defined
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
    // Get existing colors or initialize empty array
    const colors = config.modResults.resources.color || [];
    
    // Check if activityBackground already exists
    const hasActivityBackground = colors.some(
      (color) => color.$?.name === 'activityBackground'
    );
    
    // Add activityBackground if not present
    if (!hasActivityBackground) {
      colors.push({
        $: { name: 'activityBackground' },
        _: '#1a1a1a', // Dark background matching app theme
      });
      console.log('[android-colors-plugin] Added activityBackground color resource');
    }
    
    // Check if colorPrimaryDark exists (sometimes needed)
    const hasColorPrimaryDark = colors.some(
      (color) => color.$?.name === 'colorPrimaryDark'
    );
    
    if (!hasColorPrimaryDark) {
      colors.push({
        $: { name: 'colorPrimaryDark' },
        _: '#1a1a1a',
      });
      console.log('[android-colors-plugin] Added colorPrimaryDark color resource');
    }
    
    // Ensure colors array is set back
    config.modResults.resources.color = colors;
    
    return config;
  });
}

module.exports = withActivityBackgroundColor;
