[app]
title = Jinx
package.name = jinx
package.domain = org.kayjballer
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,plyer,pyjnius,android
android.archs = arm64-v8a
orientation = portrait
fullscreen = 0
android.permissions = RECORD_AUDIO,INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
