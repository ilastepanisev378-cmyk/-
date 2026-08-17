[app]
title = Seiko
package.name = seikopuzaty
package.domain = org.seiko.puzaty
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,gif,wav,ttf,json,md,txt
version = 4.0
requirements = python3,kivy==2.3.1
orientation = portrait
fullscreen = 0
android.api = 33
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
