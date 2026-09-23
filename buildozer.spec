[app]
title = Jinx
package.name = jinx
package.domain = org.kayjballer
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3==3.10.12,hostpython3==3.10.12,kivy==2.3.0,plyer,pyjnius,android,certifi
android.archs = arm64-v8a
android.add_libs_arm64_v8a = libs/arm64-v8a/*.so
orientation = portrait
fullscreen = 0
p4a.branch = develop
android.permissions = RECORD_AUDIO,INTERNET,ACCESS_NETWORK_STATE,POST_NOTIFICATIONS,VIBRATE,SET_ALARM,MODIFY_AUDIO_SETTINGS,BLUETOOTH,BLUETOOTH_ADMIN,WRITE_SETTINGS,READ_CALENDAR,WRITE_CALENDAR
android.debug_artifact = jinx-debug.apk
android.keystore = jinx.keystore
android.keyalias = jinx
android.api = 34
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
