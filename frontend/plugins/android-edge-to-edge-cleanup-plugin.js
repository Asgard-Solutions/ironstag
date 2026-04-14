const { withAndroidStyles } = require('@expo/config-plugins');

const DEPRECATED_THEME_ITEMS = new Set([
  'android:statusBarColor',
  'android:navigationBarColor',
  'android:windowDrawsSystemBarBackgrounds',
  'android:windowLayoutInDisplayCutoutMode',
]);

function withAndroidEdgeToEdgeCleanup(config) {
  return withAndroidStyles(config, (config) => {
    const styles = config.modResults.resources?.style ?? [];

    styles.forEach((style) => {
      if (!Array.isArray(style.item)) {
        return;
      }

      style.item = style.item.filter((item) => !DEPRECATED_THEME_ITEMS.has(item.$?.name));
    });

    return config;
  });
}

module.exports = withAndroidEdgeToEdgeCleanup;
