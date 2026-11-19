// SPDX-FileCopyrightText: Copyright 2026 Hokkaido contributors
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.utils

import android.content.DialogInterface
import android.text.Html
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.edit
import androidx.core.content.pm.ShortcutInfoCompat
import androidx.core.content.pm.ShortcutManagerCompat
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import androidx.navigation.NavController
import androidx.preference.PreferenceManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.yuzu.yuzu_emu.HomeNavigationDirections
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.YuzuApplication
import org.yuzu.yuzu_emu.model.Game
import org.yuzu.yuzu_emu.model.GamesViewModel

/** What picking a game does, in the game list and on the console home. */
object GameLaunch {
    /**
     * Starts [game] in its engine: its file and the firmware it needs are checked first, and it is recorded as the
     * game played last, with a launcher shortcut.
     */
    fun start(activity: AppCompatActivity, navController: NavController, game: Game) {
        if (!game.fileExists) {
            Toast.makeText(
                YuzuApplication.appContext,
                R.string.loader_error_file_not_found,
                Toast.LENGTH_LONG
            ).show()

            ViewModelProvider(activity)[GamesViewModel::class.java].reloadGames(true)
            return
        }

        val launch: () -> Unit = {
            val preferences =
                PreferenceManager.getDefaultSharedPreferences(YuzuApplication.appContext)
            preferences.edit {
                putLong(
                    game.keyLastPlayedTime,
                    System.currentTimeMillis()
                )
            }

            activity.lifecycleScope.launch {
                withContext(Dispatchers.IO) {
                    val shortcut =
                        ShortcutInfoCompat.Builder(YuzuApplication.appContext, game.path)
                            .setShortLabel(game.title)
                            .setIcon(GameIconUtils.getShortcutIcon(activity, game))
                            .setIntent(game.launchIntent)
                            .build()
                    ShortcutManagerCompat.pushDynamicShortcut(
                        YuzuApplication.appContext,
                        shortcut
                    )
                }
            }

            GameEngine.start(activity, game) {
                val action = HomeNavigationDirections.actionGlobalEmulationActivity(game, true)
                navController.navigate(action)
            }
        }

        if (NativeLibrary.gameRequiresFirmware(game.programId) && !NativeLibrary.isFirmwareAvailable()) {
            MaterialAlertDialogBuilder(activity)
                .setTitle(R.string.loader_requires_firmware)
                .setMessage(
                    Html.fromHtml(
                        activity.getString(R.string.loader_requires_firmware_description),
                        Html.FROM_HTML_MODE_LEGACY
                    )
                )
                .setPositiveButton(android.R.string.ok) { _: DialogInterface?, _: Int ->
                    launch()
                }
                .setNegativeButton(android.R.string.cancel) { _, _ -> }
                .show()
        } else {
            launch()
        }
    }
}
