package io.asgardsolution.ironstag
import expo.modules.splashscreen.SplashScreenManager

import android.os.Build
import android.os.Bundle

import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint.fabricEnabled
import com.facebook.react.defaults.DefaultReactActivityDelegate

import expo.modules.ReactActivityDelegateWrapper
import android.content.res.Configuration

class MainActivity : ReactActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    // Set the theme to AppTheme BEFORE onCreate to support
    // coloring the background, status bar, and navigation bar.
    // This is required for expo-splash-screen.
    // setTheme(R.style.AppTheme);
    // @generated begin expo-splashscreen - expo prebuild (DO NOT MODIFY) sync-f3ff59a738c56c9a6119210cb55f0b613eb8b6af
    SplashScreenManager.registerOnActivity(this)
    // @generated end expo-splashscreen
    super.onCreate(null)
  }

  /**
   * Returns the name of the main component registered from JavaScript. This is used to schedule
   * rendering of the component.
   */
  override fun getMainComponentName(): String = "main"

  /**
   * Returns the instance of the [ReactActivityDelegate]. We use [DefaultReactActivityDelegate]
   * which allows you to enable New Architecture with a single boolean flags [fabricEnabled]
   */
  override fun createReactActivityDelegate(): ReactActivityDelegate {
    return ReactActivityDelegateWrapper(
          this,
          BuildConfig.IS_NEW_ARCHITECTURE_ENABLED,
          object : DefaultReactActivityDelegate(
              this,
              mainComponentName,
              fabricEnabled
          ){})
  }

  /**
    * Align the back button behavior with Android S
    * where moving root activities to background instead of finishing activities.
    * @see <a href="https://developer.android.com/reference/android/app/Activity#onBackPressed()">onBackPressed</a>
    */
  override fun invokeDefaultOnBackPressed() {
      if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.R) {
          if (!moveTaskToBack(false)) {
              // For non-root activities, use the default implementation to finish them.
              super.invokeDefaultOnBackPressed()
          }
          return
      }

      // Use the default back button implementation on Android S
      // because it's doing more than [Activity.moveTaskToBack] in fact.
      super.invokeDefaultOnBackPressed()
  }
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


}
