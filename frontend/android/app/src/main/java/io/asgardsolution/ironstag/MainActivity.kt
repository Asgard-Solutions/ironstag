package io.asgardsolution.ironstag
import expo.modules.splashscreen.SplashScreenManager

import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint.fabricEnabled
import com.facebook.react.defaults.DefaultReactActivityDelegate

import expo.modules.ReactActivityDelegateWrapper

class MainActivity : ReactActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    // @generated begin expo-splashscreen - expo prebuild (DO NOT MODIFY) sync-f3ff59a738c56c9a6119210cb55f0b613eb8b6af
    SplashScreenManager.registerOnActivity(this)
    // @generated end expo-splashscreen
    super.onCreate(null)
    
    // Apply modern edge-to-edge handling for Android 15+
    setupEdgeToEdge()
  }

  /**
   * Handle configuration changes (orientation, screen size, etc.)
   * This ensures edge-to-edge display is maintained during orientation changes
   * and multi-window mode transitions on tablets and foldables.
   */
  override fun onConfigurationChanged(newConfig: Configuration) {
    super.onConfigurationChanged(newConfig)
    // Re-apply edge-to-edge setup after configuration changes
    setupEdgeToEdge()
  }

  /**
   * Handle multi-window mode changes (split-screen, freeform, etc.)
   * Required for Android 7.0+ multi-window support on tablets and foldables.
   */
  override fun onMultiWindowModeChanged(isInMultiWindowMode: Boolean, newConfig: Configuration) {
    super.onMultiWindowModeChanged(isInMultiWindowMode, newConfig)
    // Re-apply edge-to-edge setup when entering/exiting multi-window mode
    setupEdgeToEdge()
  }

  /**
   * Sets up edge-to-edge display using modern AndroidX APIs.
   * This replaces deprecated Window.setStatusBarColor() and Window.setNavigationBarColor() APIs.
   */
  private fun setupEdgeToEdge() {
    // Enable edge-to-edge display
    WindowCompat.setDecorFitsSystemWindows(window, false)
    
    // Get the WindowInsetsController for controlling system bars appearance
    val windowInsetsController = WindowCompat.getInsetsController(window, window.decorView)
    
    // Configure system bars appearance using modern APIs
    windowInsetsController.apply {
      // Use light status bar icons on dark background (false = light icons)
      isAppearanceLightStatusBars = false
      // Use light navigation bar icons on dark background (false = light icons)
      isAppearanceLightNavigationBars = false
    }
    
    // For Android 15+ (API 35), avoid using deprecated color APIs
    // Instead, let the system handle the colors via themes and WindowInsetsController
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.VANILLA_ICE_CREAM) {
      // Android 15+ - use transparent system bars with edge-to-edge
      window.setDecorFitsSystemWindows(false)
    } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
      // Android 11-14 - use WindowInsetsController
      window.setDecorFitsSystemWindows(false)
    } else {
      // Android 10 and below - use legacy flags with compat library
      @Suppress("DEPRECATION")
      window.decorView.systemUiVisibility = (
        View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
      )
    }
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
}
