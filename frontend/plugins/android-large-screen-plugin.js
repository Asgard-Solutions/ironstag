/**
 * Expo Config Plugin: Android 16 Large Screen & Multi-Window Support
 * 
 * This plugin modifies native Android configuration to:
 * 1. Remove orientation restrictions (android:screenOrientation)
 * 2. Enable resizable activities for tablets, foldables, and multi-window
 * 3. Add configuration change handlers for orientation and screen size
 * 
 * Required for Android 16 compliance where orientation/resizability restrictions
 * are ignored on large-screen devices.
 * 
 * @see https://developer.android.com/about/versions/16/behavior-changes-all#large-screen
 */

const { withAndroidManifest, withMainActivity, withAndroidStyles } = require('@expo/config-plugins');

/**
 * Modify AndroidManifest.xml to:
 * - Remove screenOrientation="portrait" from MainActivity
 * - Add resizeableActivity="true"
 * - Update configChanges to include density and smallestScreenSize
 */
function withLargeScreenManifest(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults;
    
    // Find the main activity
    const application = manifest.manifest.application?.[0];
    if (application?.activity) {
      application.activity.forEach((activity) => {
        const activityName = activity.$?.['android:name'];
        
        // Target MainActivity
        if (activityName === '.MainActivity') {
          // Remove orientation lock
          delete activity.$['android:screenOrientation'];
          
          // Enable resizable activity for multi-window support
          activity.$['android:resizeableActivity'] = 'true';
          
          // Update configChanges to handle more configuration changes
          // This prevents activity recreation on orientation/size changes
          const existingConfigChanges = activity.$['android:configChanges'] || '';
          const configChangesSet = new Set(existingConfigChanges.split('|').filter(Boolean));
          
          // Add additional config changes for large screen support
          configChangesSet.add('orientation');
          configChangesSet.add('screenSize');
          configChangesSet.add('screenLayout');
          configChangesSet.add('smallestScreenSize');
          configChangesSet.add('density');
          configChangesSet.add('keyboard');
          configChangesSet.add('keyboardHidden');
          configChangesSet.add('uiMode');
          
          activity.$['android:configChanges'] = Array.from(configChangesSet).join('|');
          
          console.log('[android-large-screen-plugin] Updated MainActivity:');
          console.log('  - Removed screenOrientation restriction');
          console.log('  - Set resizeableActivity=true');
          console.log(`  - configChanges: ${activity.$['android:configChanges']}`);
        }
      });
    }
    
    return config;
  });
}

/**
 * Modify styles.xml to add resizeableActivity to the theme
 * This ensures the setting is applied at the theme level as well
 */
function withLargeScreenStyles(config) {
  return withAndroidStyles(config, (config) => {
    const styles = config.modResults;
    
    // Find AppTheme style
    if (styles.resources?.style) {
      styles.resources.style.forEach((style) => {
        if (style.$?.name === 'AppTheme') {
          // Initialize items array if it doesn't exist
          if (!style.item) {
            style.item = [];
          }
          
          // Check if resizeableActivity already exists
          const hasResizeable = style.item.some(
            (item) => item.$?.name === 'android:resizeableActivity'
          );
          
          if (!hasResizeable) {
            style.item.push({
              $: { name: 'android:resizeableActivity' },
              _: 'true',
            });
            console.log('[android-large-screen-plugin] Added resizeableActivity to AppTheme');
          }
        }
      });
    }
    
    return config;
  });
}

/**
 * Main plugin export
 * Combines all modifications for Android 16 large screen compliance
 */
function withAndroidLargeScreenSupport(config) {
  console.log('[android-large-screen-plugin] Applying Android 16 large screen configuration...');
  
  // Apply manifest modifications
  config = withLargeScreenManifest(config);
  
  // Apply styles modifications  
  config = withLargeScreenStyles(config);
  
  return config;
}

module.exports = withAndroidLargeScreenSupport;
