/**
 * Expo Config Plugin: Android Large Screen Library Overrides
 * 
 * This plugin removes screenOrientation and resizability restrictions from
 * third-party library activities that don't support large screens.
 * 
 * Issue this fixes:
 * Play Store warning: "Remove resizability and orientation restrictions in your app 
 * to support large screen devices"
 * 
 * Specifically targets:
 * - com.google.mlkit.vision.codescanner.internal.GmsBarcodeScanningDelegateActivity
 * - Any other library activities with screenOrientation="PORTRAIT"
 * 
 * Uses tools:remove to override library manifest entries during manifest merging.
 */

const { withAndroidManifest } = require('@expo/config-plugins');

/**
 * Activities from third-party libraries that need orientation restrictions removed.
 * Add new activities here as Play Store flags them.
 */
const ACTIVITIES_TO_FIX = [
  'com.google.mlkit.vision.codescanner.internal.GmsBarcodeScanningDelegateActivity',
];

/**
 * Remove orientation restrictions from library activities
 */
function withLargeScreenLibraryOverrides(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    
    // Ensure we have the tools namespace
    if (!manifest.$['xmlns:tools']) {
      manifest.$['xmlns:tools'] = 'http://schemas.android.com/tools';
    }
    
    // Get application node
    const application = manifest.application?.[0];
    if (!application) {
      console.log('[android-large-screen-libs] No application node found');
      return config;
    }
    
    // Ensure activity array exists
    if (!application.activity) {
      application.activity = [];
    }
    
    // Add override entries for each problematic library activity
    ACTIVITIES_TO_FIX.forEach((activityName) => {
      // Check if override already exists
      const exists = application.activity.some(
        (activity) => activity.$?.['android:name'] === activityName
      );
      
      if (!exists) {
        // Add override activity that removes screenOrientation during manifest merge
        application.activity.push({
          $: {
            'android:name': activityName,
            'android:screenOrientation': 'unspecified',
            'android:resizeableActivity': 'true',
            'tools:replace': 'android:screenOrientation,android:resizeableActivity',
          },
        });
        console.log(`[android-large-screen-libs] Added override for: ${activityName}`);
      }
    });
    
    return config;
  });
}

module.exports = withLargeScreenLibraryOverrides;
