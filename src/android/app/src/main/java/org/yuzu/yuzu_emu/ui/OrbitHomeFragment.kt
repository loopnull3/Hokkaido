// SPDX-FileCopyrightText: Copyright 2026 Hokkaido contributors
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.ui

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.BatteryManager
import android.os.Bundle
import android.provider.DocumentsContract
import android.view.InputDevice
import android.view.KeyEvent
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.ViewModel
import androidx.navigation.fragment.findNavController
import androidx.preference.PreferenceManager
import java.io.ByteArrayInputStream
import org.json.JSONArray
import org.json.JSONObject
import org.yuzu.yuzu_emu.HomeNavigationDirections
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.YuzuApplication
import org.yuzu.yuzu_emu.features.DocumentProvider
import org.yuzu.yuzu_emu.features.settings.model.Settings
import org.yuzu.yuzu_emu.features.settings.ui.SettingsSubscreen
import org.yuzu.yuzu_emu.model.Game
import org.yuzu.yuzu_emu.model.GamesViewModel
import org.yuzu.yuzu_emu.model.HomeViewModel
import org.yuzu.yuzu_emu.utils.GameLaunch
import org.yuzu.yuzu_emu.utils.GameMetadata
import org.yuzu.yuzu_emu.utils.collect

/** Whether the console home was opened in this activity: the game list opens it once, at the start (OrbitHomeFragment.START_KEY). */
class OrbitHomeState : ViewModel() {
    var opened = false
}

/**
 * The console home: the games as a row of tiles over a starry sky, with the system icons below (assets/orbit/index.html,
 * in a WebView). The page asks the app for the games, their icons and its labels, and the app passes it the
 * controller's buttons and stick; picking a game starts it as the game list does (GameLaunch).
 */
class OrbitHomeFragment : Fragment() {
    private val gamesViewModel: GamesViewModel by activityViewModels()
    private val homeViewModel: HomeViewModel by activityViewModels()

    private var webView: WebView? = null

    // What the page reads through the bridge, on its own thread: set on the main thread
    @Volatile private var games: List<Game> = emptyList()

    @Volatile private var labels = "{}"

    @Volatile private var userName = ""

    private var stick = ""

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        labels = labelsJson()
        val web = WebView(requireContext())
        web.setBackgroundColor(Color.BLACK)
        web.settings.javaScriptEnabled = true
        web.settings.allowFileAccess = false
        web.settings.allowContentAccess = false
        web.isFocusable = true
        web.isFocusableInTouchMode = true
        web.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView,
                request: WebResourceRequest
            ): WebResourceResponse = serve(request.url)

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) = true
        }
        web.addJavascriptInterface(Bridge(), "Hokkaido")
        web.setOnKeyListener { _, keyCode, event -> onKey(keyCode, event) }
        web.setOnGenericMotionListener { _, event -> onStick(event) }
        ViewCompat.setOnApplyWindowInsetsListener(web) { view, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout()
            )
            val d = view.resources.displayMetrics.density
            js("orbit.insets(${bars.top / d},${bars.right / d},${bars.bottom / d},${bars.left / d})")
            insets
        }
        web.loadUrl("$ORIGIN/index.html")
        webView = web
        return web
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        homeViewModel.setStatusBarShadeVisibility(false)
        gamesViewModel.games.collect(viewLifecycleOwner) { list ->
            val preferences = PreferenceManager.getDefaultSharedPreferences(YuzuApplication.appContext)
            games = list.sortedWith(
                compareByDescending<Game> { preferences.getLong(it.keyLastPlayedTime, 0L) }
                    .thenBy { it.title.lowercase() }
            )
            js("orbit.refresh()")
        }
        requireActivity().onBackPressedDispatcher.addCallback(
            viewLifecycleOwner,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    // The page closes its sheet or sleep screen; at the home itself, Back leaves the app
                    webView?.evaluateJavascript("orbit.back()") { took ->
                        if (took != "true") activity?.finish()
                    }
                }
            }
        )
    }

    override fun onResume() {
        super.onResume()
        userName = NativeLibrary.getCurrentUser()?.let { NativeLibrary.getUserUsername(it) } ?: ""
        webView?.onResume()
        webView?.requestFocus()
        js("orbit.reset(); orbit.refresh()")
    }

    override fun onPause() {
        webView?.onPause()
        super.onPause()
    }

    override fun onDestroyView() {
        webView?.destroy()
        webView = null
        super.onDestroyView()
    }

    private fun js(code: String) {
        webView?.evaluateJavascript("if (window.orbit) { $code }", null)
    }

    private fun labelsJson(): String = JSONObject().apply {
        put("all", getString(R.string.orbit_all_software))
        put("empty", getString(R.string.orbit_no_games))
        put("open", getString(R.string.orbit_open))
        put("close", getString(R.string.close))
        put("cancel", getString(android.R.string.cancel))
        put("off", getString(R.string.orbit_turn_off))
        put("news", getString(R.string.orbit_news))
        put("newsBody", getString(R.string.orbit_news_description))
        put("store", getString(R.string.orbit_store))
        put("storeBody", getString(R.string.orbit_store_description))
        put("album", getString(R.string.orbit_album))
        put("albumBody", getString(R.string.orbit_album_description))
        put("controller", getString(R.string.orbit_controllers))
        put("controllerBody", getString(R.string.orbit_controllers_description))
        put("settings", getString(R.string.orbit_settings))
        put("settingsBody", getString(R.string.orbit_settings_description))
        put("sleep", getString(R.string.orbit_sleep))
        put("sleepBody", getString(R.string.orbit_sleep_description))
    }.toString()

    /** The page and the games' icons, from the app itself: nothing is loaded from the network. */
    private fun serve(url: Uri): WebResourceResponse {
        val path = url.path ?: ""
        if (url.host != HOST) return notFound()
        if (path == "/index.html") {
            return WebResourceResponse(
                "text/html",
                "utf-8",
                YuzuApplication.appContext.assets.open("orbit/index.html")
            )
        }
        if (path.startsWith("/icon/")) {
            val game = path.removePrefix("/icon/").toIntOrNull()?.let { games.getOrNull(it) }
            if (game == null || game.isLooseExeFS) return notFound()
            val data = runCatching { GameMetadata.getIcon(game.path) }.getOrNull()
            if (data == null || data.isEmpty()) return notFound()
            return WebResourceResponse("image/jpeg", null, ByteArrayInputStream(data))
        }
        return notFound()
    }

    private fun notFound() =
        WebResourceResponse("text/plain", "utf-8", 404, "Not Found", emptyMap(), ByteArrayInputStream(ByteArray(0)))

    private fun onKey(keyCode: Int, event: KeyEvent): Boolean {
        val key = when (keyCode) {
            KeyEvent.KEYCODE_DPAD_LEFT -> "L"
            KeyEvent.KEYCODE_DPAD_RIGHT -> "R"
            KeyEvent.KEYCODE_DPAD_UP -> "U"
            KeyEvent.KEYCODE_DPAD_DOWN -> "D"
            KeyEvent.KEYCODE_BUTTON_A, KeyEvent.KEYCODE_DPAD_CENTER,
            KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER -> "A"
            KeyEvent.KEYCODE_BUTTON_B -> "B"
            else -> return false
        }
        if (event.action == KeyEvent.ACTION_DOWN) {
            // B steps back inside the home only: it never leaves the app, as on a console
            js(if (key == "B") "orbit.back()" else "orbit.key('$key')")
        }
        return true
    }

    private fun onStick(event: MotionEvent): Boolean {
        if (event.source and InputDevice.SOURCE_JOYSTICK != InputDevice.SOURCE_JOYSTICK ||
            event.action != MotionEvent.ACTION_MOVE
        ) {
            return false
        }
        val x = event.getAxisValue(MotionEvent.AXIS_X) + event.getAxisValue(MotionEvent.AXIS_HAT_X)
        val y = event.getAxisValue(MotionEvent.AXIS_Y) + event.getAxisValue(MotionEvent.AXIS_HAT_Y)
        val dir = when {
            x > STICK -> "R"
            x < -STICK -> "L"
            y > STICK -> "D"
            y < -STICK -> "U"
            else -> ""
        }
        if (dir != stick) {
            stick = dir
            js("orbit.stick('$dir')")
        }
        return true
    }

    /** What the page asks of the app. Its calls come on a thread of the WebView's: anything with the UI goes to the main thread. */
    private inner class Bridge {
        @JavascriptInterface
        fun games(): String = JSONArray().apply {
            games.forEachIndexed { i, game ->
                put(
                    JSONObject()
                        .put("t", game.title.replace("[\\t\\n\\r]+".toRegex(), " "))
                        .put(
                            "i",
                            if (game.isLooseExeFS) "" else "$ORIGIN/icon/$i?v=${(game.path + game.version).hashCode()}"
                        )
                )
            }
        }.toString()

        @JavascriptInterface
        fun labels(): String = labels

        @JavascriptInterface
        fun user(): String = userName

        @JavascriptInterface
        fun battery(): Double {
            val manager = YuzuApplication.appContext.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            val level = manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
            return if (level in 0..100) level / 100.0 else -1.0
        }

        @JavascriptInterface
        fun launch(index: Int) {
            webView?.post { startGame(index) }
        }

        @JavascriptInterface
        fun action(id: String) {
            webView?.post { doAction(id) }
        }
    }

    private fun startGame(index: Int) {
        val game = games.getOrNull(index) ?: return
        val activity = activity as? AppCompatActivity ?: return
        if (!isAdded) return
        GameLaunch.start(activity, findNavController(), game)
        // A dialog may come first (Banana Native's Prepare, the firmware): the home is there again behind it
        webView?.postDelayed({ js("orbit.reset()") }, 1500)
    }

    private fun doAction(id: String) {
        if (!isAdded) return
        val nav = findNavController()
        when (id) {
            "all" -> nav.popBackStack(R.id.gamesFragment, false)
            "news" -> nav.navigate(
                HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(SettingsSubscreen.ABOUT, null)
            )
            "store" -> nav.navigate(
                HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(SettingsSubscreen.GAME_FOLDERS, null)
            )
            "profiles" -> nav.navigate(
                HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(SettingsSubscreen.PROFILE_MANAGER, null)
            )
            "controller" -> nav.navigate(
                HomeNavigationDirections.actionGlobalSettingsActivity(null, Settings.MenuTag.SECTION_INPUT)
            )
            "settings" -> nav.navigate(R.id.homeSettingsFragment)
            "album" -> {
                // Hokkaido's own files (screenshots, logs) in the phone's file browser
                val root = DocumentsContract.buildRootUri(DocumentProvider.AUTHORITY, DocumentProvider.ROOT_ID)
                val intent = Intent(Intent.ACTION_VIEW)
                    .setDataAndType(root, DocumentsContract.Root.MIME_TYPE_ITEM)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                try {
                    startActivity(intent)
                } catch (e: ActivityNotFoundException) {
                    Toast.makeText(requireContext(), R.string.orbit_album_unavailable, Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    companion object {
        private const val HOST = "hokkaido.home"
        private const val ORIGIN = "https://$HOST"
        private const val STICK = 0.5f

        /** The setting: the app opens on the console home (on by default), else on the game list. */
        const val START_KEY = "orbit_home_start"

        fun opensAtStart(context: Context): Boolean =
            PreferenceManager.getDefaultSharedPreferences(context).getBoolean(START_KEY, true)
    }
}
