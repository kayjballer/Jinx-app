[app]
title = Jinx
package.name = jinx
package.domain = org.kayjballer
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,plyer,pyjnius,android,certifi,sqlite3
android.archs = arm64-v8a
android.add_libs_arm64_v8a = libs/arm64-v8a/*.so
orientation = portrait
fullscreen = 0
p4a.branch = develop
android.permissions = RECORD_AUDIO,INTERNET,ACCESS_NETWORK_STATE,POST_NOTIFICATIONS,VIBRATE,SET_ALARM,MODIFY_AUDIO_SETTINGS,BLUETOOTH,BLUETOOTH_ADMIN,WRITE_SETTINGS,READ_CALENDAR,WRITE_CALENDAR
android.debug_artifact = jinx-debug.apk
android.keystore = jinx.keystore
android.keyalias = jinx
android.api = 33
android.minapi = 21
android.ndk = 27b
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
