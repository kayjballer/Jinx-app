[app]
title = Jinx
package.name = jinx
package.domain = org.kayjballer
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3,kivy,pyjnius,android,plyer,certifi
android.archs = arm64-v8a
android.add_libs_arm64_v8a = libs/arm64-v8a/*.so
orientation = portrait
fullscreen = 0
p4a.branch = develop
android.permissions = RECORD_AUDIO,INTERNET,ACCESS_NETWORK_STATE,POST_NOTIFICATIONS,VIBRATE,SET_ALARM,MODIFY_AUDIO_SETTINGS,BLUETOOTH,BLUETOOTH_ADMIN,WRITE_SETTINGS,READ_CALENDAR,WRITE_CALENDAR
# (retiré pour simplifier)
# (retiré temporairement)
# (retiré temporairement)
android.api = 33
android.minapi = 21
# android.ndk = (p4a choisit automatiquement)
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
