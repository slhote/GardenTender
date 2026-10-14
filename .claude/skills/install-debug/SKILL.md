---
name: install-debug
description: Build the GardenTender debug APK and install it on the connected Android phone over adb (wireless debugging). Use when asked to install, deploy, or push the app to the phone for debugging.
---

Install the debug build on the connected phone.

1. Check a device is connected:

   ```powershell
   & adb devices
   ```

   If the state is `unauthorized`, ask the user to accept the prompt on the phone, then re-check.

   If no device is listed with state `device`, ask the user for the phone's IP address and port. The wireless debugging port changes whenever Wireless debugging is toggled or Wi-Fi reconnects, so they need to read it from the phone's Wireless debugging screen ("IP address & Port", not the pairing dialog). Do not guess or reuse an old port. Once they reply, connect and re-check:

   ```powershell
   adb connect <ip:port>
   adb devices
   ```

   If it still fails, report the `adb connect` error and stop.

2. Build and install. The first build after a dependency change can take several minutes, so run it in the background and wait for the completion notification instead of polling:

   ```powershell
   cd C:\Users\Seth\Source\Repos\GardenTender\GardenTender.Android; .\gradlew.bat :app:installDebug
   ```

3. Report the result in one or two lines: "Installed on 1 device." on success, or the Gradle error on failure.
